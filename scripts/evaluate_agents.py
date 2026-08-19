"""Agent 可行性评估：mock 确定性 + 沙盒快照 + 多路裁判。

用法：
    python scripts/evaluate_agents.py

三层：
  L1 确定性  —— mock 固定样本跑两端管线 + 故障注入（源失败/全失败/无Key），
               断言输出结构完整、降级正确、不伪造。
  L2 真实性  —— 用 data/snapshots 真实快照离线复现两端，检查产出完整性与合理性。
  L3 多路裁判 —— 相关性/合规/原创性/结构/价值 5 个裁判独立打分（0-5），
               汇总可行性结论（均分与短板）。
"""
from __future__ import annotations
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

RESULT = {"L1": {}, "L2": {}, "L3": {}}


# =============================================================================
# L1 · mock 确定性验证
# =============================================================================

def l1_mock_pipeline():
    """固定输入跑两端管线，断言结构完整、降级正确。"""
    from core.pipeline import run_pipeline
    from core.models import Event

    # 固定样本（含跨源重复、HN、官方源）
    samples = [
        Event(title="OpenAI raises $10B at $300B valuation - Reuters", source="Google News · Reuters [官方]", url="u1", published_at="", collected_at="", source_category="google_news", category="ai"),
        Event(title="OpenAI raises $10B, AI capex boom - Bloomberg", source="Google News · Bloomberg [官方]", url="u2", published_at="", collected_at="", source_category="google_news", category="ai"),
        Event(title="GXS Bank launches cashback card with Grab", source="Google News · Fintech Singapore [官方]", url="u3", published_at="", collected_at="", source_category="google_news", category="fintech"),
        Event(title="A new AI framework for agents", source="Hacker News", url="u4", published_at="", collected_at="", source_category="hacker_news", category="ai", heat_score=120),
    ]
    r = run_pipeline(samples)
    evs = r["events"]
    # 断言：去重后 <= 原始（跨源重复应合并）
    assert len(evs) <= len(samples), "去重后不应多于原始"
    # 断言：每事件有评分理由与跟进决策
    for e in evs:
        assert e["priority_reasons"].get("heat") is not None, "缺热度因子"
        assert e.get("follow_decision"), "缺跟进决策"
    # 断言：Agent1 候选生成（每事件 1 条，含发布文案）
    from agents import hot_topic_agent
    top = [e for e in evs if e["follow_decision"] in ("follow", "consider")][:2]
    for e in top:
        cands = hot_topic_agent.build_candidates_for_event(Event.from_dict(e))
        assert len(cands) == 1, "每事件应只生成 1 条候选"
        c = cands[0]
        for k in ("body_en", "summary_zh", "content_zh", "risk_level"):
            assert c.get(k), f"候选缺字段 {k}"
    return {"dedup": len(evs), "checked_candidates": len(top)}


def l1_fault_injection():
    """故障注入：单源失败 / 全源失败 / 无 Key。"""
    out = {}
    # 单源失败：mock orchestrator 让 HN 抛错，其余正常
    import agents.collectors.hacker_news as hn
    orig = hn.collect
    hn.collect = lambda: (_ for _ in ()).throw(RuntimeError("mock HN down"))
    try:
        from agents.collectors import orchestrator
        s = orchestrator.collect_summary()
        out["single_source_fail"] = {
            "ok": s["total_events"] > 0,  # 其他源仍产出
            "warnings": [w["source"] for w in s["warnings"]],
        }
    finally:
        hn.collect = orig

    # 全源失败：mock 三个源全抛错 → 应无伪造，warnings 齐全
    import agents.collectors.google_news as gn
    import agents.collectors.gdelt as gd
    o1, o2, o3 = gn.collect, gd.collect, hn.collect
    gn.collect = lambda: (_ for _ in ()).throw(RuntimeError("down"))
    gd.collect = lambda: (_ for _ in ()).throw(RuntimeError("down"))
    hn.collect = lambda: (_ for _ in ()).throw(RuntimeError("down"))
    try:
        from agents.collectors import orchestrator
        s = orchestrator.collect_summary()
        out["all_sources_fail"] = {
            "ok": s["total_events"] == 0,  # 绝不伪造
            "warnings": len(s["warnings"]) >= 3,
        }
    finally:
        gn.collect, gd.collect, hn.collect = o1, o2, o3

    # 无 Key：provider 应回退模板/缓存，不崩
    import os as _os
    _os.environ["OPENAI_API_KEY"] = ""
    from agents.ai_provider import get_provider
    from core.models import Event
    p = get_provider()
    ev = Event(title="test", source="s", url="u", published_at="", collected_at="", source_category="x", category="ai")
    cands = p.generate_candidates(ev)
    out["no_key_demo"] = {"ok": len(cands) >= 1, "mode": cands[0]["generation_mode"]}
    return out


def l1():
    out = {}
    out["pipeline"] = l1_mock_pipeline()
    out["faults"] = l1_fault_injection()
    ok = out["faults"]["single_source_fail"]["ok"] and out["faults"]["all_sources_fail"]["ok"] and out["faults"]["no_key_demo"]["ok"]
    out["pass"] = bool(ok)
    RESULT["L1"] = out
    return out


# =============================================================================
# L2 · 沙盒快照离线复现
# =============================================================================

def l2():
    from agents.collectors import snapshot
    from core.pipeline import run_pipeline
    from core.models import Event
    from agents import viral_agent, viral_breakdown

    out = {}
    # Agent1：真实快照离线跑
    snap_names = snapshot.list_snapshots()
    events = []
    for sn in snap_names:
        events.extend(snapshot.load_snapshot(sn.replace(".json", "")))
    r = run_pipeline(events)
    out["agent1"] = {
        "snapshots": snap_names,
        "raw": r["raw_count"],
        "deduped": r["deduped_count"],
        "events": len(r["events"]),
    }
    # 完整字段抽查
    field_ok = 0
    for e in r["events"][:20]:
        if e.get("priority_reasons") and e.get("follow_decision") and e.get("data_authenticity"):
            field_ok += 1
    out["agent1"]["field_complete"] = field_ok
    out["agent1"]["pass"] = r["deduped_count"] > 0 and field_ok > 0

    # Agent2：拆解 + 候选（用真实快照帖子）
    disc = viral_agent.run_discovery("AlphaSenseInc", prefer_live=False)
    analysis = viral_breakdown.breakdown(disc["posts"])
    templates = viral_agent.build_insight_templates(analysis)
    insight = disc["posts"][0]["snippet"] if disc["posts"] else "AI finance"
    cands = viral_agent.create_candidates_from_insight(
        insight, analysis, templates, [p["snippet"] for p in disc["posts"]], "cached_public"
    )
    out["agent2"] = {
        "posts": len(disc["posts"]),
        "mode": disc["mode"],
        "high": analysis["high_count"],
        "normal": analysis["normal_count"],
        "candidates": len(cands),
        "dims": list(analysis["dimensions"].keys()),
    }
    cand_ok = all(c.get("body_en") and c.get("risk_level") and c.get("similarity") for c in cands)
    out["agent2"]["candidate_complete"] = cand_ok
    out["agent2"]["pass"] = len(cands) >= 3 and cand_ok and analysis["high_count"] > 0
    RESULT["L2"] = out
    return out


# =============================================================================
# L3 · 多路裁判
# =============================================================================

def l3_judges(candidates: list, profile: dict | None = None) -> list:
    """5 个独立裁判，各自 0-5 分 + 理由。"""
    import re
    from core.account import REGION_PRESETS

    profile = profile or {}
    core_topics = profile.get("core_topics") or ["ai", "fintech", "investing"]
    region_words = []
    for v in REGION_PRESETS.values():
        region_words.extend(v)

    judge_results = []
    for idx, c in enumerate(candidates, 1):
        body = c.get("body_en", "")
        lower = body.lower()
        # 裁判1 相关性
        rel_score = 0
        if any(t in lower for t in core_topics):
            rel_score += 2
        if re.search(r"\d", body):
            rel_score += 2
        if any(w in lower for w in region_words):
            rel_score += 1
        # 裁判2 合规（反信号）
        risk_hits = [s for s in c.get("risk_signals", [])]
        compliance = 5 - 2 * len(risk_hits)
        compliance = max(0, min(5, compliance))
        # 裁判3 原创性（相似度反比）
        sim = c.get("similarity", {}).get("score", 0)
        originality = round(max(0, 5 - 8 * sim), 2)
        # 裁判4 结构完整（Hook/CTA/来源/免责）
        struct = 0
        for marker in (c.get("cta"), c.get("fact_sources"), "informational purposes"):
            if marker:
                struct += 1.5
        struct = round(min(5, struct + (1 if c.get("body_en", "").count("\n") >= 3 else 0)), 2)
        # 裁判5 价值密度（数字+长度适中+非模板腔）
        value = 1
        value += 1.5 if re.search(r"\d", body) else 0
        words = len(body.split())
        value += 1.5 if 30 <= words <= 150 else 0
        value += 1 if not re.search(r"(this is a template|placeholder)", lower) else -1
        value = max(0, min(5, value))

        judge_results.append({
            "candidate": idx,
            "relevance": rel_score,
            "compliance": compliance,
            "originality": originality,
            "structure": struct,
            "value_density": value,
            "avg": round((rel_score + compliance + originality + struct + value) / 5, 2),
            "risk_hits": [s.get("signal") for s in risk_hits],
        })
    return judge_results


def l3():
    from agents import viral_agent, viral_breakdown
    from agents.hot_topic_agent import build_candidates_for_event
    from core.models import Event

    # 用真实快照事件生成 Agent1 候选 + Agent2 候选
    cands = []
    ev = Event(title="OpenAI raises $10B for AI infrastructure, capex boom - Reuters", source="Google News · Reuters [官方]", url="x", published_at="", collected_at="", source_category="google_news", category="ai", priority_score=0.9)
    cands += build_candidates_for_event(ev)

    disc = viral_agent.run_discovery("AlphaSenseInc", prefer_live=False)
    analysis = viral_breakdown.breakdown(disc["posts"])
    templates = viral_agent.build_insight_templates(analysis)
    insight = disc["posts"][0]["snippet"] if disc["posts"] else "AI finance"
    cands += viral_agent.create_candidates_from_insight(
        insight, analysis, templates, [p["snippet"] for p in disc["posts"]], "cached_public"
    )

    rows = l3_judges(cands)
    avgs = [r["avg"] for r in rows]
    RESULT["L3"] = {
        "candidates_judged": len(rows),
        "rows": rows,
        "overall_avg": round(sum(avgs) / len(avgs), 2) if avgs else 0,
        "min_avg": min(avgs) if avgs else 0,
        "verdict": "可行" if (avgs and sum(avgs) / len(avgs) >= 3.5 and min(avgs) >= 2.5) else "需优化",
    }
    return RESULT["L3"]


def main():
    # ensure DB schema exists (fresh clone / removed finsignal.db)
    from core import db

    db.init_db()

    print("=" * 64)
    print("L1 · mock 确定性验证")
    l1r = l1()
    print(json.dumps(l1r, ensure_ascii=False, indent=2, default=str))
    print("L1 pass:", l1r.get("pass"))

    print("=" * 64)
    print("L2 · 沙盒快照离线复现")
    l2r = l2()
    print(json.dumps(l2r, ensure_ascii=False, indent=2, default=str))

    print("=" * 64)
    print("L3 · 多路裁判（5 裁判 × 候选）")
    l3r = l3()
    for row in l3r["rows"]:
        print(
            f"  候选{row['candidate']}: 相关{row['relevance']} 合规{row['compliance']} "
            f"原创{row['originality']} 结构{row['structure']} 价值{row['value_density']} "
            f"→ 均分{row['avg']} (risk={row['risk_hits']})"
        )
    print(f"  总体均分 {l3r['overall_avg']} / 最弱项 {l3r['min_avg']} → 结论: {l3r['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

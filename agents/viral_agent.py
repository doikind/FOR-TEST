"""Viral-breakdown & re-creation Agent (Agent #2).

完整闭环：X 内容发现（真实接口或快照回退）→ 同账号高表现 vs 普通筛选
→ 六维度拆解（选题/Hook/结构/信息密度/CTA/互动设计）→ 证据分级
(OBSERVED/INFERRED/UNKNOWN) → 沉淀可复用结构 → 围绕同一洞察生成 ≥3 条
原创候选 → 写入资产库并支持后续模拟表现记录（simulated_demo）。
"""
import json
from typing import Any, Dict, List

from agents import ai_provider, benchmark_data, content_safety, similarity, x_discovery
from core import db


def run_discovery(account: str = "Finimize", prefer_live: bool = True) -> Dict[str, Any]:
    """Discover posts for the benchmark account (live or snapshot fallback)."""
    return x_discovery.load_or_discover(account, prefer_live=prefer_live)


def save_live_snapshot(disc: Dict[str, Any], account: str = "Finimize") -> str:
    """Persist live-discovered posts as a real public data snapshot (cached_public)."""
    import datetime as dt
    import os

    from core import config

    payload = {
        "account": account,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "generated_from": "x.com public profile page",
        "data_authenticity": "cached_public",
        "note": "真实公开数据快照：由 x.com 公开页面解析生成（真实 Post ID/时间/全文；互动计数为页面占位值，未使用）",
        "posts": disc["posts"],
    }
    os.makedirs(config.SNAPSHOTS_DIR, exist_ok=True)
    path = os.path.join(config.SNAPSHOTS_DIR, f"x_{account.lower()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def _analyze(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    from agents import viral_breakdown

    result = viral_breakdown.breakdown(posts)
    return result


def build_insight_templates(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    from agents import viral_breakdown

    return viral_breakdown.structure_templates(analysis)


def _historical_candidate_texts(limit: int = 20) -> List[str]:
    """Prior candidate bodies from the review pool (avoid self-repetition)."""
    from agents import review

    texts = []
    for c in review.list_candidates(status=None)[:limit]:
        body = c.get("content", {}).get("body_en", "")
        if body:
            texts.append(body)
    return texts


def create_candidates_from_insight(
    insight_title: str,
    analysis: Dict[str, Any],
    templates: List[Dict[str, Any]],
    benchmark_texts: List[str],
    authenticity: str = "simulated_demo",
    style: Dict[str, bool] | None = None,
) -> List[Dict[str, Any]]:
    """Generate >=3 original candidates around the same real insight, using the
    distilled structure templates (hook / numbers / CTA patterns).

    Each candidate carries the full field set incl. bilingual notes,
    similarity check vs benchmark AND historical candidates, and financial
    risk check.
    """
    from core.models import Event

    ev = Event(
        title=insight_title,
        source="Agent2 · 拆解洞察",
        url="",
        published_at="",
        collected_at="",
        source_category="viral_breakdown",
        data_authenticity=authenticity,
        category="general",
    )

    provider = ai_provider.get_provider()
    angles = provider.suggest_angles(ev, n=3)
    angles_zh = provider.suggest_angles_zh(ev, n=3)
    candidates = provider.generate_candidates(ev, angles)

    # fold structure-template hints into the candidates
    hint_lines = []
    for t in templates:
        for e in t.get("elements", []):
            hint_lines.append(e)
    dims = analysis.get("dimensions", {})

    # --- breakdown-driven STYLE: high-performing features actually shape the
    # post structure (hook question / number-first / CTA question).
    # An explicit style from an applied structure template overrides it. ---
    style = dict(style or {})
    if dims.get("hook", {}).get("diff", 0) > 0 and "hook_question" not in style:
        style["hook_question"] = True
    if dims.get("information_density", {}).get("diff", 0) > 0 and "number_first" not in style:
        style["number_first"] = True
    if dims.get("cta", {}).get("diff", 0) > 0 and "cta_question" not in style:
        style["cta_question"] = True

    # ORIGINAL rewrite: turn the insight into 3 original posts (never verbatim)
    from agents.rewrite import generate_original_posts

    original_posts = generate_original_posts(insight_title, n=3, style=style)

    for i, c in enumerate(candidates):
        op = original_posts[i] if i < len(original_posts) else original_posts[0]
        c["topic"] = insight_title
        c["angle"] = op["angle_en"]
        c["angle_zh"] = op["angle_zh"]
        c["summary_en"] = provider.summarize(ev)
        c["summary_zh"] = provider.summarize_zh(ev)
        c["source_info"] = {
            "source": "Agent2 · 拆解洞察（原创改写）",
            "url": "",
            "published_at": "",
            "collected_at": "",
            "source_category": "viral_breakdown",
        }
        c["data_authenticity"] = authenticity
        c["structure_hints"] = hint_lines
        c["hook_style"] = op["hook_style"]
        c["facts_used"] = op.get("facts_used", {})
        c["fact_sources"] = [f"对标内容快照（{authenticity}）"]

        # ORIGINAL body: the rewritten post (no source text pasted verbatim)
        c["body_en"] = op["body_en"]
        c["cta"] = op["cta"]
        c["body_zh"] = ""  # Agent2 candidates are English-only (no Chinese)

        # dimension-derived notes (which observed drivers informed this candidate)
        driver_notes = []
        for dim, d in dims.items():
            if d.get("inferred_driver") and d.get("diff", 0) != 0:
                driver_notes.append(f"{dim}: {d['inferred_driver'][:60]}")
        c["insight_drivers"] = driver_notes

        # similarity check vs benchmark content + historical candidates
        corpus = benchmark_texts + _historical_candidate_texts()
        sim = similarity.check_similarity(c["body_en"], corpus)
        c["similarity"] = sim
        content_safety.check_candidate(c, sim["score"], sim["benchmark_hit"])
        c["risk_notes"] = []
        if sim["flagged"]:
            if sim["benchmark_hit"] in benchmark_texts:
                c["risk_notes"].append(f"与对标内容相似度过高({sim['score']:.3f})，需改写")
            else:
                c["risk_notes"].append(f"与历史候选相似度过高({sim['score']:.3f})，需改写")
    return candidates


def persist_to_asset_library(
    insight_title: str,
    candidates: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    templates: List[Dict[str, Any]],
    authenticity: str,
) -> Dict[str, Any]:
    """Write approved-worthy candidates into asset library (draft) + review pool.

    HIGH-risk candidates never enter the asset library. Returns summary.

    topic_key uniqueness: repeated generation for the same insight must not
    collide, so each persist batch gets a unique timestamp suffix.
    """
    import datetime as dt

    db.init_db()
    conn = db.get_conn()
    ids = []
    batch = dt.datetime.now().strftime("%Y%m%d%H%M%S%f")
    try:
        for i, c in enumerate(candidates, 1):
            topic_key = f"agent2::{insight_title[:40]}::{batch}::candidate-{i}"
            cur = conn.execute(
                """
                INSERT INTO candidates (
                    topic_key, source, pipeline, category, priority_score,
                    risk_level, status, data_authenticity, content_json
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    topic_key,
                    "Agent2",
                    "content_creation",
                    "general",
                    0.0,
                    c.get("risk_level", "LOW"),
                    "Draft",
                    c.get("data_authenticity", authenticity),
                    json.dumps(c, ensure_ascii=False),
                ),
            )
            cid = int(cur.lastrowid)
            ids.append(cid)
            if c.get("risk_level") != "HIGH":
                conn.execute(
                    "INSERT INTO assets (candidate_id, title, status, data_authenticity) VALUES (?,?,?,?)",
                    (cid, c.get("topic", ""), "draft", c.get("data_authenticity", authenticity)),
                )
        # persist the distilled structure template as a reusable asset
        for t in templates:
            conn.execute(
                "INSERT INTO assets (title, status, structure_template, data_authenticity) VALUES (?,?,?,?)",
                (t.get("name", "structure template"), "draft",
                 json.dumps(t, ensure_ascii=False), authenticity),
            )
        conn.commit()
    finally:
        conn.close()
    return {
        "candidate_ids": ids,
        "candidate_count": len(ids),
        "template_count": len(templates),
    }


def record_performance(asset_id: int, metrics: Dict[str, Any]) -> None:
    """Record simulated post-performance for an asset (always simulated_demo)."""
    from agents import review

    review.simulate_publish(asset_id, metrics)

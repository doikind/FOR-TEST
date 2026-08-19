"""Hot-topic-to-pool Agent (Agent #1).

完整闭环：真实热点 → 去重 → 优先级排序 → 账号相关性判断（是否值得跟进）
→ 双语摘要/角度 → 生成英文候选（含中文说明）→ 加入待审核内容池。
采用/驳回由 agents.review 记录，并据此调整后续推荐权重。
"""
from __future__ import annotations
import json
from typing import Any, Dict, List

from agents import ai_provider, content_safety
from core import db
from core.models import Event


def build_candidates_for_event(
    event: Event,
    angles: List[str] | None = None,
    angles_zh: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """Generate ONE bilingual candidate (EN body + ZH notes) per event.

    The review pool holds one candidate per topic (no 3-way split). The
    candidate carries a Chinese summary + Chinese content gloss for quick
    review. The English body is produced by the ADAPTATION engine: the
    headline's facts are re-worded and re-structured (never copied verbatim).
    Runs similarity-independent risk check.
    """
    from agents import adaptation, zh_support

    provider = ai_provider.get_provider()
    angles = angles or provider.suggest_angles(event, n=1)
    angles_zh = angles_zh or provider.suggest_angles_zh(event, n=1)

    # adapted body: original rewrite of the headline facts
    op = adaptation.adapt_one(event.title, event.source)

    # Chinese support for this exact event
    zh = zh_support.enrich_zh(event.title)
    summary_zh = zh_support.summarize_zh(event.title, event.source, event.category)

    c = {
        "topic": event.title,
        "angle": op["angle_en"],
        "angle_zh": angles_zh[0] if angles_zh else op["angle_zh"],
        "body_en": op["body_en"],
        "cta": op["cta"],
        "hook_style": "adapted",
        "summary_en": provider.summarize(event),
        "summary_zh": summary_zh,
        "content_zh": f"中文概括：本条候选围绕「{zh['topic_zh']}」展开，角度为「{op['angle_zh']}」。正文以英文发布，发布前请核对来源。",
        "title_zh": zh["title_zh"],
        "keywords_zh": zh["keywords_zh"],
        "fact_sources": [event.url],
        "source_info": {
            "source": event.source,
            "url": event.url,
            "published_at": event.published_at,
            "collected_at": event.collected_at,
            "source_category": event.source_category,
        },
        "data_authenticity": event.data_authenticity,
        "relevance": event.priority_reasons.get("relevance", {}),
        "facts_used": op.get("facts_used", {}),
    }
    # risk check (no benchmark similarity for hot-topic path)
    content_safety.check_candidate(c, 0.0, "")
    c["risk_notes"] = []
    return [c]


def persist_to_pool(event: Event, candidates: List[Dict[str, Any]]) -> List[int]:
    """Insert candidates into the review pool (status Draft) and asset draft.

    topic_key unique per candidate (same topic yields multiple candidates);
    a batch timestamp prevents collisions when the same event is re-processed.
    HIGH-risk candidates are never written to the asset library.
    """
    import datetime as dt

    db.init_db()
    conn = db.get_conn()
    ids = []
    batch = dt.datetime.now().strftime("%Y%m%d%H%M%S%f")
    try:
        base_key = event.dedup_key or event.title
        for i, c in enumerate(candidates, 1):
            topic_key = f"{base_key}::{batch}::candidate-{i}"
            cur = conn.execute(
                """
                INSERT INTO candidates (
                    topic_key, source, pipeline, category, priority_score,
                    risk_level, status, data_authenticity, content_json
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    topic_key,
                    event.source,
                    "hot_topics",
                    event.category,
                    event.priority_score,
                    c.get("risk_level", "LOW"),
                    "Draft",
                    c.get("data_authenticity", event.data_authenticity),
                    json.dumps(c, ensure_ascii=False),
                ),
            )
            cid = int(cur.lastrowid)
            ids.append(cid)
            if c.get("risk_level") != "HIGH":
                conn.execute(
                    "INSERT INTO assets (candidate_id, title, status, data_authenticity) VALUES (?,?,?,?)",
                    (cid, c.get("topic", ""), "draft", c.get("data_authenticity", "")),
                )
        conn.commit()
    finally:
        conn.close()
    return ids


def run_agent(events: List[Event]) -> Dict[str, Any]:
    """Run Agent #1 over ranked events; generate candidates for follow/consider.

    Returns summary: {followed, pooled, skipped, candidates}.
    """
    pooled_ids: List[int] = []
    generated = 0
    skipped = 0
    for ev in events:
        if ev.follow_decision not in ("follow", "consider"):
            skipped += 1
            continue
        cands = build_candidates_for_event(ev)
        ids = persist_to_pool(ev, cands)
        pooled_ids.extend(ids)
        generated += len(cands)
    return {
        "generated": generated,
        "pooled": len(pooled_ids),
        "skipped": skipped,
        "candidate_ids": pooled_ids,
    }

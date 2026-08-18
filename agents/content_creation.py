"""Content creation — generate >=3 original English X candidates.

Combines a real market insight (event) with viral-breakdown structure
templates, produces candidates with the full required field set, runs a
TF-IDF similarity check against benchmark content, and runs the financial
risk check. Writes candidates into the review pool + asset library (draft).
"""
import json
from typing import Any, Dict, List

from agents import ai_provider, benchmark_data, content_safety, similarity
from core import db
from core.models import Event


def create_candidates(
    event: Event,
    benchmark_texts: List[str] | None = None,
    templates: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Generate >=3 candidates for one real insight, with full field set."""
    provider = ai_provider.get_provider()
    angles = provider.suggest_angles(event, n=3)
    candidates = provider.generate_candidates(event, angles)

    benchmark_texts = benchmark_texts or []
    # fold structure-template hints into the hook/structure fields
    template_hints = []
    if templates:
        for t in templates:
            template_hints.extend(t.get("elements", []))

    enriched = []
    for c in candidates:
        # fill the full required field set
        c["topic"] = event.title
        c["fact_sources"] = c.get("fact_sources", [event.url])
        c["target_interaction"] = c.get("target_interaction", "reply / discussion")
        c["hook"] = c.get("hook", event.title[:120])
        c["structure"] = c.get("structure", "claim → context → source → CTA")
        c["cta"] = c.get("cta", "What's your read on this?")
        c["structure_hints"] = template_hints
        c["data_authenticity"] = event.data_authenticity
        c["source_category"] = event.source_category

        # similarity check
        sim = similarity.check_similarity(c["body_en"], benchmark_texts)
        c["similarity"] = sim

        # risk check (with similarity score folded in)
        content_safety.check_candidate(c, sim["score"], sim["benchmark_hit"])

        # risk notes: if similarity flagged, note it
        c["risk_notes"] = []
        if sim["flagged"]:
            c["risk_notes"].append(f"high similarity to benchmark ({sim['score']:.3f}); rewrite required")
        enriched.append(c)

    return enriched


def persist_candidates(event: Event, candidates: List[Dict[str, Any]], pipeline: str = "content_creation") -> List[int]:
    """Write candidates into review pool (status Draft) and asset library (draft)."""
    db.init_db()
    conn = db.get_conn()
    ids = []
    try:
        base_key = event.dedup_key or event.title
        for i, c in enumerate(candidates, 1):
            if c.get("risk_level") == "HIGH":
                # Blocked: goes to pool for viewing but never into asset library
                status = "Draft"
            else:
                status = "Draft"
            # topic_key unique per candidate (same topic yields multiple
            # distinct candidates; keep them all).
            topic_key = f"{base_key}::candidate-{i}"
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
                    pipeline,
                    event.category,
                    event.priority_score,
                    c.get("risk_level", "LOW"),
                    status,
                    c.get("data_authenticity", event.data_authenticity),
                    json.dumps(c, ensure_ascii=False),
                ),
            )
            cid = int(cur.lastrowid)
            ids.append(cid)
            # asset library: only non-Blocked candidates enter as draft
            if c.get("risk_level") != "HIGH":
                conn.execute(
                    "INSERT INTO assets (candidate_id, title, status, data_authenticity) VALUES (?,?,?,?)",
                    (cid, c.get("topic", ""), "draft", c.get("data_authenticity", "")),
                )
        conn.commit()
    finally:
        conn.close()
    return ids

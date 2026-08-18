"""Review pool + asset library workflows.

Five-state candidate review (Draft / Needs Revision / Pending Review /
Approved / Rejected), human-only approve, audit log, and asset library with
simulated publish (labeled simulated_demo). Feedback weights are transparent
rule adjustments (+0.05 approve / -0.03 reject, bounded -0.10..+0.10), never
presented as model training.
"""
import json
from typing import Any, Dict, List, Optional

from core import db

VALID_STATUSES = ("Draft", "Needs Revision", "Pending Review", "Approved", "Rejected")

# Preset rejection categories — feedback becomes explainable & classifiable.
REJECT_REASONS = (
    "角度重复",      # duplicate angle vs another candidate
    "风险过高",      # financial/risk concerns too high to fix quickly
    "价值偏低",      # low information value for the audience
    "偏离账号定位",  # off-brand / out of the account's positioning
    "事实存疑",      # factual concerns, source unverified
    "其他",          # other
)

FEEDBACK_DIMENSIONS = ("ai", "fintech", "investing", "crypto", "general")


def list_candidates(status: str | None = None, pipeline: str | None = None) -> List[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        q = "SELECT * FROM candidates"
        conds, args = [], []
        if status:
            conds.append("status = ?")
            args.append(status)
        if pipeline:
            conds.append("pipeline = ?")
            args.append(pipeline)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY id DESC"
        rows = conn.execute(q, args).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["content"] = json.loads(d.pop("content_json") or "{}")
            out.append(d)
        return out
    finally:
        conn.close()


# --- five-state workflow ------------------------------------------------------
# Allowed transitions (from -> to). Final states (Approved / Rejected) are
# terminal: nothing may leave them.
_TRANSITIONS = {
    "Draft": {"Pending Review"},
    "Needs Revision": {"Pending Review"},   # resubmit after editing
    "Pending Review": {"Approved", "Rejected", "Needs Revision"},
    "Approved": set(),
    "Rejected": set(),
}
_TERMINAL = ("Approved", "Rejected")


def _assert_transition(current: str, target: str) -> None:
    if current in _TERMINAL:
        raise ValueError(f"终态 {current} 不可再变更")
    if target not in _TRANSITIONS.get(current, set()):
        raise ValueError(f"非法状态流转: {current} → {target}")


def _next_revision(conn, candidate_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM review_log WHERE candidate_id=? AND action='request_revision'",
        (candidate_id,),
    ).fetchone()
    return int(row["c"]) + 1


def submit_for_review(candidate_id: int, note: str = "") -> None:
    """Submit for review: Draft -> Pending Review, or Needs Revision -> Pending Review.

    Revision candidates carry a revision counter in the log so the flow is
    auditable (v1 → v2 → ...).
    """
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("candidate not found")
        content = json.loads(row["content_json"] or "{}")
        if content.get("risk_level") == "HIGH":
            raise ValueError("HIGH (Blocked) candidates cannot enter review")
        _assert_transition(row["status"], "Pending Review")
        rev = _next_revision(conn, candidate_id)
        conn.execute("UPDATE candidates SET status = 'Pending Review' WHERE id = ?", (candidate_id,))
        conn.execute(
            "INSERT INTO review_log (candidate_id, action, note) VALUES (?,?,?)",
            (candidate_id, "submit", f"{note or '提交审核'} (v{rev})"),
        )
        conn.commit()
    finally:
        conn.close()


def approve(candidate_id: int, note: str = "") -> None:
    """Human approve: candidate -> Approved; enter asset library; +0.05 weight."""
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("candidate not found")
        content = json.loads(row["content_json"] or "{}")
        if content.get("risk_level") == "HIGH":
            raise ValueError("HIGH (Blocked) candidates cannot be approved")
        _assert_transition(row["status"], "Approved")
        conn.execute("UPDATE candidates SET status = 'Approved' WHERE id = ?", (candidate_id,))
        conn.execute(
            "INSERT INTO review_log (candidate_id, action, note) VALUES (?,?,?)",
            (candidate_id, "approve", note),
        )
        # ensure asset exists as approved
        asset = conn.execute("SELECT id FROM assets WHERE candidate_id = ?", (candidate_id,)).fetchone()
        if asset:
            conn.execute("UPDATE assets SET status = 'approved' WHERE candidate_id = ?", (candidate_id,))
        else:
            conn.execute(
                "INSERT INTO assets (candidate_id, title, status, data_authenticity) VALUES (?,?,?,?)",
                (candidate_id, content.get("topic", ""), "approved", content.get("data_authenticity", "")),
            )
        conn.commit()
    finally:
        conn.close()
    # online-learning supervision signal: approve = label 1
    try:
        from agents import feedback_model

        features = feedback_model.extract_features(content, {
            "category": row["category"],
            "heat": 0.0, "recency": 0.0, "category_match": 0.0,
            "relevance": content.get("relevance"),
            "source_category": content.get("source_info", {}).get("source_category", ""),
            "source": content.get("source_info", {}).get("source", ""),
        })
        feedback_model.add_sample(candidate_id, 1, features, row["category"] or "")
    except Exception:  # noqa: BLE001 — sample logging must never break review
        pass
    # transparent rule weight adjustment (not model training)
    _apply_feedback_weight("approve", row["category"])


def reject(candidate_id: int, reason: str, note: str = "") -> None:
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        _assert_transition(row["status"], "Rejected")
        content = json.loads(row["content_json"] or "{}")
        conn.execute("UPDATE candidates SET status = 'Rejected', reject_reason = ? WHERE id = ?", (reason, candidate_id))
        conn.execute(
            "INSERT INTO review_log (candidate_id, action, reason, note) VALUES (?,?,?,?)",
            (candidate_id, "reject", reason, note),
        )
        conn.commit()
    finally:
        conn.close()
    if row:
        # online-learning supervision signal: reject = label 0
        try:
            from agents import feedback_model

            features = feedback_model.extract_features(content, {
                "category": row["category"],
                "heat": 0.0, "recency": 0.0, "category_match": 0.0,
                "relevance": content.get("relevance"),
                "source_category": content.get("source_info", {}).get("source_category", ""),
                "source": content.get("source_info", {}).get("source", ""),
            })
            feedback_model.add_sample(candidate_id, 0, features, row["category"] or "")
        except Exception:  # noqa: BLE001
            pass
        _apply_feedback_weight("reject", row["category"])


def reject_reason_stats() -> List[Dict[str, Any]]:
    """Count rejections by preset category (explainable feedback loop)."""
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT reason, COUNT(*) AS cnt FROM review_log WHERE action='reject' AND reason IS NOT NULL GROUP BY reason ORDER BY cnt DESC"
        ).fetchall()
        return [{"reason": r["reason"], "count": r["cnt"]} for r in rows]
    finally:
        conn.close()


def update_candidate_content(candidate_id: int, body_en: str, note: str = "") -> None:
    """Edit & save the publishable English text of a candidate.

    Persists body_en into content_json and records an edit in the audit log.
    """
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("candidate not found")
        content = json.loads(row["content_json"] or "{}")
        content["body_en"] = body_en
        conn.execute(
            "UPDATE candidates SET content_json = ? WHERE id = ?",
            (json.dumps(content, ensure_ascii=False), candidate_id),
        )
        conn.execute(
            "INSERT INTO review_log (candidate_id, action, note) VALUES (?,?,?)",
            (candidate_id, "edit_content", note or "修改发布文案"),
        )
        conn.commit()
    finally:
        conn.close()


def request_revision(candidate_id: int, note: str) -> None:
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("candidate not found")
        _assert_transition(row["status"], "Needs Revision")
        conn.execute("UPDATE candidates SET status = 'Needs Revision', revision_note = ? WHERE id = ?", (note, candidate_id))
        conn.execute(
            "INSERT INTO review_log (candidate_id, action, note) VALUES (?,?,?)",
            (candidate_id, "request_revision", note),
        )
        conn.commit()
    finally:
        conn.close()


def review_log(candidate_id: int | None = None) -> List[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        if candidate_id is not None:
            rows = conn.execute("SELECT * FROM review_log WHERE candidate_id = ? ORDER BY id", (candidate_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM review_log ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- asset library & simulated publish ----------------------------------------

def list_assets(status: str | None = None) -> List[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        q = "SELECT * FROM assets"
        if status:
            q += " WHERE status = ?"
            rows = conn.execute(q, (status,)).fetchall() if status else conn.execute(q).fetchall()
        else:
            rows = conn.execute(q).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["performance"] = json.loads(d.pop("performance_json") or "{}")
            out.append(d)
        return out
    finally:
        conn.close()


def simulate_publish(asset_id: int, performance: Dict[str, Any]) -> None:
    """Record simulated post-performance; always labeled simulated_demo."""
    conn = db.get_conn()
    try:
        performance = dict(performance)
        performance["data_authenticity"] = "simulated_demo"
        conn.execute(
            "UPDATE assets SET status = 'published', performance_json = ?, data_authenticity = ?, published_at = datetime('now') WHERE id = ?",
            (json.dumps(performance, ensure_ascii=False), "simulated_demo", asset_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_completed(asset_ids: List[int]) -> int:
    """Batch mark assets as published (已完成). Returns affected count."""
    if not asset_ids:
        return 0
    conn = db.get_conn()
    try:
        placeholders = ",".join("?" for _ in asset_ids)
        cur = conn.execute(
            f"UPDATE assets SET status = 'published', published_at = datetime('now') WHERE id IN ({placeholders})",
            asset_ids,
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_assets(asset_ids: List[int]) -> int:
    """Batch 'delete' assets: archive them into assets_deleted (soft delete),
    so the deleted items remain viewable in the asset library. Returns count."""
    if not asset_ids:
        return 0
    conn = db.get_conn()
    try:
        placeholders = ",".join("?" for _ in asset_ids)
        rows = conn.execute(
            f"SELECT * FROM assets WHERE id IN ({placeholders})", asset_ids
        ).fetchall()
        for r in rows:
            conn.execute(
                """
                INSERT INTO assets_deleted (
                    candidate_id, title, status, structure_template,
                    performance_json, data_authenticity, published_at
                ) VALUES (?,?,?,?,?,?,?)
                """,
                (
                    r["candidate_id"], r["title"], "deleted",
                    r["structure_template"], r["performance_json"],
                    r["data_authenticity"], r["published_at"],
                ),
            )
        cur = conn.execute(f"DELETE FROM assets WHERE id IN ({placeholders})", asset_ids)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def list_deleted_assets() -> List[Dict[str, Any]]:
    """List archived (soft-deleted) assets."""
    conn = db.get_conn()
    try:
        rows = conn.execute(
            "SELECT id, candidate_id, title, status, structure_template, performance_json, data_authenticity, deleted_at FROM assets_deleted ORDER BY id DESC"
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["performance"] = json.loads(d.pop("performance_json") or "{}")
            out.append(d)
        return out
    finally:
        conn.close()


def estimate_performance(candidate_content: Dict[str, Any]) -> Dict[str, Any]:
    """Rule-based engagement estimate for a candidate (simulated reference).

    Uses observable content features (numbers, question hook, CTA question,
    length, emoji) to produce a transparent reference estimate. Always
    labeled as a rule-based estimate, never presented as real results.
    """
    import re

    body = candidate_content.get("body_en", "") or ""
    hook = candidate_content.get("hook_style", "") or ""
    cta = candidate_content.get("cta", "") or ""
    text = body.lower()

    score = 1.0
    reasons = []
    if re.search(r"\d", body):
        score += 0.25
        reasons.append("含数字")
    if "question" in hook or "?" in body.splitlines()[0] if body else False:
        score += 0.20
        reasons.append("提问式Hook")
    if "?" in cta or any(k in cta for k in ("what", "how", "where", "your read")):
        score += 0.15
        reasons.append("提问式CTA")
    words = len(body.split())
    if 30 <= words <= 110:
        score += 0.15
        reasons.append("篇幅适中")
    if len(re.findall(r"[\U0001F300-\U0001FAFF]", body)) > 0:
        score += 0.10
        reasons.append("含emoji")

    base_likes, base_replies, base_reposts = 80, 8, 15
    return {
        "estimated_likes": round(base_likes * score),
        "estimated_replies": round(base_replies * score),
        "estimated_reposts": round(base_reposts * score),
        "reasons": reasons,
        "note": "规则化预估参考（基于内容特征），非真实运营数据",
        "data_authenticity": "simulated_demo",
    }


def feedback_weight(decision: str, category: str) -> Optional[Dict[str, Any]]:
    """Transparent rule weight adjustment for a category dimension.

    approve -> +0.05, reject -> -0.03, bounded [-0.10, +0.10].
    Returns {before, after, dimension} or None if category unknown.
    """
    if category not in FEEDBACK_DIMENSIONS:
        return None
    delta = 0.05 if decision == "approve" else -0.03
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT weight FROM feedback_weights WHERE dimension = ?", (category,)).fetchone()
        before = row["weight"] if row else 0.0
        after = max(-0.10, min(0.10, round(before + delta, 2)))
        conn.execute(
            """
            INSERT INTO feedback_weights (dimension, weight, last_action) VALUES (?,?,?)
            ON CONFLICT(dimension) DO UPDATE SET weight = excluded.weight, last_action = excluded.last_action,
                updated_at = datetime('now')
            """,
            (category, after, decision),
        )
        conn.commit()
        return {"dimension": category, "before": before, "after": after, "delta": delta}
    finally:
        conn.close()


def _apply_feedback_weight(decision: str, category: str) -> None:
    """Internal: apply the transparent rule weight adjustment (swallow unknown)."""
    try:
        feedback_weight(decision, category)
    except Exception:  # noqa: BLE001 — weight adjustment must never break review
        pass


def feedback_snapshot() -> List[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        rows = conn.execute("SELECT dimension, weight, last_action, updated_at FROM feedback_weights ORDER BY dimension").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

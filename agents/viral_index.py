"""Viral Index scoring model for Agent 1 (hot topics → content pool).

Replaces the flat priority ranking with a weighted, explainable "爆款指数":

    ViralIndex = 0.20*Timeliness + 0.25*Actionability
               + 0.20*Visual appeal + 0.20*Novelty
               + 0.15*Authority/Relevance

Each dimension scores 0..100; the composite is 0..100. Only events whose
composite score is >= VIRAL_THRESHOLD (70) are eligible to enter the final
candidate pool. Every dimension carries a short reason so the score is fully
explainable in the UI.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List

VIRAL_THRESHOLD = 70.0

# --- dimension weights ------------------------------------------------------
WEIGHTS = {
    "timeliness": 0.20,
    "actionability": 0.25,
    "visual": 0.20,
    "novelty": 0.20,
    "authority": 0.15,
}

# --- text signals -----------------------------------------------------------
_ACTION_WORDS = (
    "ipo", "launches", "launched", "launch", "acquires", "acquired",
    "raises", "raised", "funding", "approves", "approved", "unveils",
    "unveiled", "announces", "announced", "partner", "partnership",
    "regulation", "regulator", "policy", "guidance", "forecast", "report",
    "reports", "earnings", "results", "sanction", "ban", "clears",
    "surpasses", "breaks", "sets record", "expands", "plans", "debut",
)
_NOVELTY_WORDS = (
    "first", "first-ever", "breakthrough", "launch", "debut", "unveils",
    "new record", "record", "milestone", "world's first", "revolution",
    "transform", "disrupt", "novel", "unprecedented", "opens",
    "introduces", "introduced", "pioneer",
)
_VISUAL_WORDS = (
    "surge", "surges", "plunge", "plunges", "soars", "soared", "jumps",
    "jumped", "falls", "rises", "record", "top", "best", "biggest",
    "largest", "fastest", "vs", "beats", "misses", "outperform",
    "overtakes", "hits", "tops",
)
_AUTHORITATIVE_SOURCES = (
    "reuters", "bloomberg", "ft.com", "wsj", "financial times", "cnbc",
    "fintech singapore", "fintech global", "techcrunch", "the edge",
    "monetary authority", "mas", "bbc",
)


def _timeliness_score(published_at: str) -> float:
    """0..100: fresher = higher. Mirrors the pipeline recency logic."""
    if not published_at:
        return 50.0
    import datetime as dt

    try:
        dtobj = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        age_h = (now - dtobj).total_seconds() / 3600.0
        if age_h <= 0:
            return 100.0
        if age_h <= 6:
            return 100.0
        if age_h <= 24:
            return 80.0
        if age_h <= 72:
            return 60.0
        if age_h <= 168:
            return 40.0
        return 20.0
    except Exception:  # noqa: BLE001
        return 50.0


def _actionability_score(title: str) -> float:
    """0..100: how actionable is the story (numbers, deals, policy moves)."""
    t = title.lower()
    score = 30.0
    reasons: List[str] = []
    if re.search(r"\d", title):
        score += 25.0
        reasons.append("含具体数字")
    if re.search(r"\$[\d.]+\s?[mbk]?|[\d.]+%", title, re.I):
        score += 15.0
        reasons.append("含金额/百分比")
    hits = [w for w in _ACTION_WORDS if re.search(rf"\b{w}\b", t)]
    if hits:
        score += 20.0
        reasons.append("含行动信号(" + ", ".join(hits[:3]) + ")")
    if re.search(r"against|to buy|to sell|advisory|investor|investors", t):
        score += 10.0
        reasons.append("面向投资者决策")
    # multiple concrete facts (numbers + deal words) → strongly actionable
    if re.search(r"\d", title) and hits:
        score += 15.0
        reasons.append("数字+行动叠加")
    return round(min(100.0, score), 1), reasons


def _visual_score(title: str) -> float:
    """0..100: visual/format potential for social posts."""
    t = title.lower()
    score = 30.0
    reasons: List[str] = []
    if re.search(r"\d", title):
        score += 20.0
        reasons.append("含数字(易做信息图)")
    hits = [w for w in _VISUAL_WORDS if re.search(rf"\b{w}\b", t)]
    if hits:
        score += 15.0
        reasons.append("情绪化对比词(" + ", ".join(hits[:3]) + ")")
    if re.search(r"[:?—–-]", title):
        score += 15.0
        reasons.append("含冒号/问号(Hook 潜力)")
    if 40 <= len(title) <= 110:
        score += 15.0
        reasons.append("标题长度适中")
    if re.search(r"\b(top|best|biggest|largest|fastest|record|most)\b", t):
        score += 10.0
        reasons.append("榜单型标题")
    return round(min(100.0, score), 1), reasons


def _novelty_score(title: str) -> float:
    """0..100: is this a fresh/breakthrough story vs routine news."""
    t = title.lower()
    score = 30.0
    reasons: List[str] = []
    hits = [w for w in _NOVELTY_WORDS if re.search(rf"\b{w}\b", t)]
    if hits:
        score += 30.0
        reasons.append("首次/突破信号(" + ", ".join(hits[:3]) + ")")
    if re.search(r"\b(new|fresh|first)\b", t) or "new " in t:
        score += 10.0
        reasons.append("新事件")
    if re.search(r"surprise|unexpected|suddenly|shock|stuns", t):
        score += 15.0
        reasons.append("意外性")
    # big-number contrast: unusual magnitude implies a non-routine story
    if re.search(r"\$[\d.]+\s?(billion|bn|million|m)\b", t, re.I):
        score += 15.0
        reasons.append("大额数字(非常规)")
    return round(min(100.0, score), 1), reasons


def _authority_score(ev: Any) -> float:
    """0..100: source authority + account-profile relevance + big amounts."""
    src = (ev.get("source") or "").lower()
    title = (ev.get("title") or "").lower()
    score = 35.0
    reasons: List[str] = []
    if any(s in src for s in _AUTHORITATIVE_SOURCES):
        score += 25.0
        reasons.append("权威来源")
    rel = (ev.get("priority_reasons") or {}).get("relevance", {}) or {}
    rel_score = float(rel.get("score") or 0.0)
    if rel_score:
        score += 25.0 * max(0.0, min(1.0, rel_score))
        reasons.append(f"账号相关性 {rel_score:.2f}")
    # headline magnitude (SGD/USD amounts) boosts perceived importance
    if re.search(r"\$[\d.]+\s?(billion|bn|million|m|k)\b", title, re.I):
        score += 15.0
        reasons.append("大额金额提升重要性")
    return round(min(100.0, score), 1), reasons


def score_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the viral index for one standardized event dict.

    Returns {viral_index, dims, reasons, qualifies}.
    """
    title = ev.get("title") or ""
    timeliness, _ = _timeliness_score(ev.get("published_at") or ""), None
    action, action_why = _actionability_score(title)
    visual, visual_why = _visual_score(title)
    novelty, novelty_why = _novelty_score(title)
    authority, authority_why = _authority_score(ev)

    dims = {
        "timeliness": round(timeliness, 1),
        "actionability": action,
        "visual": visual,
        "novelty": novelty,
        "authority": authority,
    }
    total = sum(WEIGHTS[k] * dims[k] for k in WEIGHTS)
    reasons = {
        "timeliness": _timeliness_note(ev.get("published_at") or "", timeliness),
        "actionability": action_why,
        "visual": visual_why,
        "novelty": novelty_why,
        "authority": authority_why,
    }
    return {
        "viral_index": round(total, 1),
        "dims": dims,
        "reasons": reasons,
        "qualifies": total >= VIRAL_THRESHOLD,
    }


def _timeliness_note(published_at: str, score: float) -> List[str]:
    if not published_at:
        return ["无发布时间，按中性分"]
    import datetime as dt

    try:
        dtobj = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        age_h = max(0, (now - dtobj).total_seconds() / 3600.0)
        return [f"发布 {age_h:.0f} 小时前"]
    except Exception:  # noqa: BLE001
        return ["时间格式异常"]


def rank_top10(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Score all events, sort by viral index desc, return the Top 10.

    Each entry gets: viral_index, dims, reasons, qualifies, core_insight.
    """
    scored = []
    for ev in events:
        s = score_event(ev)
        s["event"] = ev
        scored.append(s)
    scored.sort(key=lambda s: s["viral_index"], reverse=True)
    top = scored[:10]
    # attach a one-line core insight per entry
    from agents import zh_support

    for s in top:
        title = s["event"].get("title") or ""
        zh = zh_support.enrich_zh(title)
        s["core_insight"] = zh.get("title_zh", title)
    return top


def top10_board(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """High-level board for the UI: counts + the ranked list."""
    top = rank_top10(events)
    qualified = [t for t in top if t["qualifies"]]
    return {
        "total_scored": len(events),
        "top10": top,
        "qualified_count": len(qualified),
        "threshold": VIRAL_THRESHOLD,
        "weights": WEIGHTS,
    }

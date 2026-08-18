"""Pipeline: standardize -> dedup -> score -> (later) follow decision."""
import datetime as dt
import hashlib
import re
from typing import List

from core import config
from core.models import Event

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "for",
    "with", "as", "at", "by", "is", "are", "was", "were", "be", "been", "this",
    "that", "these", "those", "it", "its", "from", "how", "why", "what", "who",
    "when", "will", "would", "can", "could", "should", "may", "might", "your",
    "you", "we", "they", "he", "she", "not", "no", "do", "does", "did",
}

_CATEGORY_RULES = [
    ("ai", ("ai", "artificial", "llm", "openai", "anthropic", "model", "machine learning", "deepmind", "agent")),
    ("crypto", ("crypto", "bitcoin", "ethereum", "blockchain", "defi", "stablecoin", "token", "coin")),
    ("fintech", ("fintech", "payment", "bank", "digital bank", "remit", "lending", "wallet", "neobank")),
    ("investing", ("invest", "market", "stock", "fund", "etf", "trading", "valuation", "ipo", "earnings", "m&a", "merger", "acquisition")),
]


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    tokens = [w for w in t.split() if w and w not in _STOPWORDS]
    return " ".join(tokens)


def classify(title: str) -> str:
    t = title.lower()
    for cat, toks in _CATEGORY_RULES:
        if any(tok in t for tok in toks):
            return cat
    return "general"


def _dedup_key(title: str, source: str) -> str:
    return hashlib.md5(f"{normalize_title(title)}|{source}".encode("utf-8")).hexdigest()


def standardize(events: List[Event]) -> List[Event]:
    """Fill normalized_title, category, dedup_key on each event."""
    for ev in events:
        ev.normalized_title = normalize_title(ev.title)
        ev.category = classify(ev.title)
        ev.dedup_key = _dedup_key(ev.title, ev.source)
    return events


def dedupe(events: List[Event], threshold: float | None = None) -> List[Event]:
    """Dedup near-duplicate titles via TF-IDF cosine similarity.

    Uses scikit-learn TfidfVectorizer. Falls back to exact normalized-title
    matching if sklearn is unavailable (still deterministic and non-fabricating).
    Returns deduplicated list with merged_from populated on the survivor.
    """
    threshold = config.DEDUP_THRESHOLD if threshold is None else threshold
    if not events:
        return events

    keep: List[Event] = []
    for ev in events:
        ev.normalized_title = ev.normalized_title or normalize_title(ev.title)

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        texts = [ev.normalized_title for ev in events]
        if len(set(texts)) < 2:
            # All identical normalized titles: keep first (highest heat).
            return _keep_first(events)

        vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        try:
            matrix = vec.fit_transform(texts)
            sim = cosine_similarity(matrix)
        except ValueError:
            return _keep_first(events)

        merged = [False] * len(events)
        for i in range(len(events)):
            if merged[i]:
                continue
            for j in range(i + 1, len(events)):
                if merged[j]:
                    continue
                if sim[i][j] >= threshold:
                    # Merge j into i (i survives); keep higher heat as survivor.
                    if events[j].heat_score > events[i].heat_score:
                        events[i], events[j] = events[j], events[i]
                        # swap similarity rows not needed since we only mark merged
                    events[i].merged_from.append(
                        {"title": events[j].title, "source": events[j].source, "url": events[j].url}
                    )
                    merged[j] = True
            keep.append(events[i])
        return keep
    except Exception:  # noqa: BLE001 — fallback to exact normalized-title dedup
        return _dedupe_fallback(events)


def _keep_first(events: List[Event]) -> List[Event]:
    best = max(events, key=lambda e: e.heat_score or 0)
    for ev in events:
        if ev is not best:
            best.merged_from.append(
                {"title": ev.title, "source": ev.source, "url": ev.url}
            )
    return [best]


def _dedupe_fallback(events: List[Event]) -> List[Event]:
    seen = {}
    result: List[Event] = []
    for ev in events:
        key = ev.normalized_title
        if key in seen:
            seen[key].merged_from.append(
                {"title": ev.title, "source": ev.source, "url": ev.url}
            )
        else:
            seen[key] = ev
            result.append(ev)
    return result


def _recency_score(published_at: str) -> float:
    if not published_at:
        return 0.5
    try:
        dtobj = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        age_h = (now - dtobj).total_seconds() / 3600.0
        if age_h <= 0:
            return 1.0
        if age_h <= 6:
            return 1.0
        if age_h <= 24:
            return 0.8
        if age_h <= 72:
            return 0.6
        if age_h <= 168:
            return 0.4
        return 0.2
    except Exception:  # noqa: BLE001
        return 0.5


_CATEGORY_MATCH = {"ai": 1.0, "fintech": 1.0, "investing": 0.9, "crypto": 0.8, "general": 0.5}

# Weak heat proxy for RSS events (no real engagement signal):
# title contains numbers, big-name entities, authoritative source, or
# published in high-engagement hours → mild boost so ranking differentiates.
_AUTHORITATIVE_SOURCES = (
    "reuters", "bloomberg", "ft.com", "wsj", "financial times", "cnbc",
    "fintech singapore", "fintech global", "techcrunch", "the edge",
)
_ENTITY_NAMES = (
    "openai", "anthropic", "nvidia", "apple", "google", "microsoft", "meta",
    "amazon", "mas", "singapore", "grab", "revolut", "blackrock", "jpmorgan",
    "goldman", "nasdaq", "bitcoin", "ethereum",
)
_HIGH_ENGAGEMENT_HOURS = (7, 8, 9, 12, 13, 17, 18, 19)  # UTC-ish proxies


def _rss_heat_proxy(ev: Event) -> float:
    """Deterministic weak heat estimate for events without real engagement."""
    title = (ev.title or "").lower()
    score = 0.40
    if re.search(r"\d", title):
        score += 0.15
    if any(e in title for e in _ENTITY_NAMES):
        score += 0.15
    src = (ev.source or "").lower()
    if any(s in src for s in _AUTHORITATIVE_SOURCES):
        score += 0.10
    try:
        dtobj = dt.datetime.fromisoformat((ev.published_at or "").replace("Z", "+00:00"))
        if dtobj.hour in _HIGH_ENGAGEMENT_HOURS:
            score += 0.10
    except Exception:  # noqa: BLE001
        pass
    return round(min(1.0, score), 3)


def _load_feedback_weights() -> dict:
    """Read category feedback weights (transparent rule adjustment)."""
    try:
        from core import db

        conn = db.get_conn()
        try:
            rows = conn.execute("SELECT dimension, weight FROM feedback_weights").fetchall()
            return {r["dimension"]: r["weight"] for r in rows}
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — DB not initialized / no weights yet
        return {}


def score(events: List[Event]) -> List[Event]:
    """Compute heat/recency/category factors and a combined priority score.

    Feedback factor: once the online-learning model is warm (>= MIN_SAMPLES
    approve/reject samples), the model's P(approve) drives the feedback
    term; before that, the transparent rule weights are used (cold start).
    """
    heats = [e.heat_score for e in events if e.heat_score > 0]
    max_heat = max(heats) if heats else 1.0
    feedback = _load_feedback_weights()

    # warm online model?
    try:
        from agents import feedback_model

        model_warm = feedback_model.sample_count() >= feedback_model.MIN_SAMPLES
    except Exception:  # noqa: BLE001
        model_warm = False

    for ev in events:
        # heat factor: normalize against max observed heat (or 1 if absent)
        if ev.heat_score > 0 and max_heat > 0:
            ev.heat_score = round(ev.heat_score / max_heat, 3)
        else:
            # no real heat signal (RSS) → weak deterministic proxy, so ranking
            # still differentiates rather than flattening everything at 0.5
            ev.heat_score = _rss_heat_proxy(ev)
        ev.recency_score = round(_recency_score(ev.published_at), 3)
        ev.category_score = round(_CATEGORY_MATCH.get(ev.category, 0.5), 3)

        if model_warm:
            # model-driven: P(approve) in [-1, 1] centered at 0
            try:
                from agents import feedback_model

                feats = feedback_model.extract_features(
                    {"body_en": ev.title},
                    {
                        "category": ev.category,
                        "heat": ev.heat_score,
                        "recency": ev.recency_score,
                        "category_match": ev.category_score,
                        "relevance": ev.priority_reasons.get("relevance", {}),
                        "source_category": ev.source_category,
                        "source": ev.source,
                    },
                )
                p = feedback_model.predict_proba(feats)
                ev.feedback_score = round((p - 0.5) * 2.0, 3) if p is not None else 0.0
            except Exception:  # noqa: BLE001
                ev.feedback_score = 0.0
            ev.priority_reasons["feedback_mode"] = "online_model"
        else:
            ev.feedback_score = round(feedback.get(ev.category, 0.0), 3)
            ev.priority_reasons["feedback_mode"] = "rule_weights"

        priority = (
            0.5 * ev.heat_score
            + 0.25 * ev.recency_score
            + 0.15 * ev.category_score
            + 0.10 * (1.0 + ev.feedback_score)
        )
        ev.priority_score = round(priority, 3)
        ev.priority_reasons.update({
            "heat": ev.heat_score,
            "heat_source": "real" if ev.heat_score != _rss_heat_proxy(ev) else "rss_proxy",
            "recency": ev.recency_score,
            "category": ev.category_score,
            "category_name": ev.category,
            "feedback": ev.feedback_score,
        })

    events.sort(key=lambda e: e.priority_score, reverse=True)
    return events


def run_pipeline(events: List[Event], annotate_follow: bool = True) -> dict:
    """Run standardize -> dedup -> score -> follow decision; return summary."""
    events = standardize(events)
    raw_count = len(events)
    deduped = dedupe(events)
    deduped = score(deduped)
    if annotate_follow:
        from core.follow import annotate

        annotate(deduped)
    return {
        "raw_count": raw_count,
        "deduped_count": len(deduped),
        "removed_count": raw_count - len(deduped),
        "events": [ev.to_dict() for ev in deduped],
    }

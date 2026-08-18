"""Viral breakdown — compare high vs normal performing content.

Computes an explainable relative performance score (never raw like count),
groups posts, extracts six-dimension features, labels each conclusion with
evidence level OBSERVED / INFERRED / UNKNOWN, and distills reusable
structure templates. All benchmark post data is labeled with its
authenticity tag (cached_public for real public snapshots, simulated_demo
for de-identified demo data).
"""
import datetime as dt
import re
from typing import Any, Dict, List

from core.models import Event


# --- relative performance score -------------------------------------------------

def _normalize_metric(value, min_v, max_v):
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)


def relative_performance_score(posts: List[Dict[str, Any]]) -> None:
    """Attach an explainable relative score per post (same account/time window).

    Two modes:
      - engagement-available: weighted normalized likes/reposts/replies
        (used for repo snapshots that carry real public metrics).
      - engagement-unknown (live X page): public engagement counts are NOT
        rendered by X for anonymous visitors, so we must NOT claim them.
        Instead we score observable derived features (length, info density,
        emoji, list structure, CTA presence) and mark the metric source as
        UNKNOWN. This never fabricates likes/replies/reposts.
    """
    if not posts:
        return

    # Are engagement metrics real (non-zero variance) or placeholder?
    likes = [p.get("metrics", {}).get("likes") or 0 for p in posts]
    replies = [p.get("metrics", {}).get("replies") or 0 for p in posts]
    reposts = [p.get("metrics", {}).get("reposts") or 0 for p in posts]
    has_real_metrics = (
        max(likes) > 3 or max(replies) > 0 or max(reposts) > 0
    ) and max(likes) != min(likes)

    if has_real_metrics:
        min_l, max_l = min(likes), max(likes)
        min_r, max_r = min(replies), max(replies)
        min_x, max_x = min(reposts), max(reposts)
        for p in posts:
            m = p.get("metrics", {})
            nl = _normalize_metric(m.get("likes", 0), min_l, max_l)
            nr = _normalize_metric(m.get("replies", 0), min_r, max_r)
            nx = _normalize_metric(m.get("reposts", 0), min_x, max_x)
            score = round(0.5 * nl + 0.3 * nx + 0.2 * nr, 3)
            p["relative_score"] = score
            p["score_factors"] = {
                "likes_norm": round(nl, 3),
                "reposts_norm": round(nx, 3),
                "replies_norm": round(nr, 3),
                "metric_source": "engagement",
            }
        return

    # Engagement unavailable → observable feature-based relative score.
    feats = [_extract_features(p) for p in posts]
    keys = ["length_words", "info_density_digits", "interaction_emoji",
            "interaction_hashtags", "structure_list", "cta_present"]
    for k in keys:
        vals = [float(f[k]) for f in feats]
        lo, hi = min(vals), max(vals)
        span = hi - lo if hi > lo else 1.0
        for p, f in zip(posts, feats):
            f[f"{k}_norm"] = round((f[k] - lo) / span, 3)
    for p, f in zip(posts, feats):
        score = round(
            0.30 * f["length_words_norm"]
            + 0.20 * f["info_density_digits_norm"]
            + 0.20 * f["interaction_emoji_norm"]
            + 0.10 * f["structure_list_norm"]
            + 0.10 * f["cta_present_norm"]
            + 0.10 * f["interaction_hashtags_norm"],
            3,
        )
        p["relative_score"] = score
        p["score_factors"] = {
            "length_norm": f["length_words_norm"],
            "density_norm": f["info_density_digits_norm"],
            "emoji_norm": f["interaction_emoji_norm"],
            "metric_source": "observable_features",
        }
        p["metrics_note"] = (
            "X 公开页面未向匿名访客渲染互动计数（非公开指标），"
            "相对表现基于可观察派生特征计算；互动数据标记为 UNKNOWN，不虚构。"
        )


_RETWEET_PREFIXES = ("rt by ", "r to ", "retweet", "🔁 ")

# Finance / AI / investing topic tokens — high-performance content must be
# on-brand (financial markets, fintech, AI, investing), not entertainment.
_FINANCE_TOKENS = (
    "earnings", "revenue", "revenue", "stock", "stocks", "market", "markets",
    "financial", "finance", "bank", "banks", "invest", "investing", "investor",
    "investors", "fund", "funding", "etf", "etfs", "ipo", "valuation", "trading",
    "ai", "artificial intelligence", "machine learning", "llm", "openai",
    "anthropic", "nvidia", "semiconductor", "chip", "chips", "tech", "technology",
    "fintech", "crypto", "bitcoin", "ethereum", "blockchain", "data center",
    "analyst", "analysts", "ceo", "cfos", "equity", "yield", "margin", "guidance",
    "revenue", "quarterly", "fiscal", "growth", "price", "prices", "billion",
    "million", "forecast", "outlook", "portfolio", "asset", "assets", "research",
    "infrastructure", "capex", "capital", "startup", "startups", "venture",
)


def _is_retweet(post: Dict[str, Any]) -> bool:
    text = (post.get("snippet") or post.get("text") or "").lower()
    return any(text.startswith(p) or text.lstrip().startswith(p) for p in _RETWEET_PREFIXES)


def _is_finance_related(post: Dict[str, Any]) -> bool:
    """High-performance content must relate to finance / AI / investing.

    Short tokens ('ai') match on word boundaries to avoid false positives
    like 'trailer' containing 'ai'; longer phrases match as substrings.
    """
    text = (post.get("snippet") or post.get("text") or "").lower()
    for tok in _FINANCE_TOKENS:
        if len(tok) <= 2:
            import re

            if re.search(rf"\b{re.escape(tok)}\b", text):
                return True
        elif tok in text:
            return True
    return False


def _has_substance(post: Dict[str, Any]) -> bool:
    """A post qualifies as a high-performance candidate only if it carries
    real information: enough length, or numbers + named entities. Short
    fragments / one-liners do not qualify."""
    text = post.get("snippet") or post.get("text") or ""
    words = len(text.split())
    has_num = bool(re.search(r"\d", text))
    has_entity = bool(re.search(r"\$[A-Z]{1,5}\b|[A-Z][a-z]{2,}\s+[A-Z]", text))
    return words >= 30 or (has_num and words >= 12) or (has_entity and words >= 15)


def split_groups(posts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Split into high vs normal with quality gates.

    High-performance group requirements:
      - NOT a retweet (RT/repost are re-shares, not original content)
      - finance / AI / investing related (on-brand, not entertainment)
      - has substance (length or facts) — one-liners never qualify
      - ranked by relative score within qualifying posts

    Normal group = everything else (retweets, off-topic, fragments, low score).
    """
    if not posts:
        return {"high": [], "normal": []}

    qualified = [
        p for p in posts
        if not _is_retweet(p)
        and _is_finance_related(p)
        and _has_substance(p)
        and p.get("relative_score", 0) > 0
    ]
    qualified.sort(key=lambda p: p.get("relative_score", 0), reverse=True)

    n = len(qualified)
    if n < 2:
        # too few qualifying posts — be conservative: nothing is 'high'
        return {"high": [], "normal": posts, "threshold": None}

    mid = n // 2
    high = qualified[:mid]
    normal = [p for p in posts if p not in high]
    threshold = qualified[mid - 1]["relative_score"] if high else None
    return {"high": high, "normal": normal, "threshold": threshold}


# --- six-dimension feature extraction -----------------------------------------

_CTA_WORDS = ("what's your", "what do you", "share", "comment", "reply", "follow", "read more", "link in", "check out", "thoughts?", "agree?")
_HOOK_QUESTIONS = ("?", "why", "how", "what if", "imagine", "the truth", "nobody", "stop", "warning")


def _extract_features(post: Dict[str, Any]) -> Dict[str, Any]:
    text = post.get("text", "") or ""
    body = post.get("snippet", "") or text
    lower = body.lower()
    n_words = len(body.split())
    n_sentences = len(re.findall(r"[.!?]", body)) or 1
    n_links = len(re.findall(r"https?://", body))
    n_digits = len(re.findall(r"\d", body))
    n_hashtags = len(re.findall(r"#\w+", body))
    n_emoji = len(re.findall(r"[\U0001F300-\U0001FAFF]", body))

    return {
        "topic": post.get("topic", "general"),
        "length_words": n_words,
        "hook_question": "?" in body or any(k in lower for k in ("why", "how", "what if")),
        "hook_strong_opener": any(k in lower for k in _HOOK_QUESTIONS),
        "structure_sentences": n_sentences,
        "structure_list": bool(re.search(r"^\s*[-*•]\s", body, re.M)) or bool(re.search(r"\d+\.\s", body)),
        "info_density_digits": n_digits,
        "info_density_links": n_links,
        "cta_present": any(k in lower for k in _CTA_WORDS),
        "interaction_hashtags": n_hashtags,
        "interaction_emoji": n_emoji,
        "interaction_mentions": len(re.findall(r"@\w+", body)),
    }


# --- evidence-level breakdown ---------------------------------------------------

def breakdown(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run relative score, grouping, feature extraction, and evidence labeling."""
    relative_performance_score(posts)
    groups = split_groups(posts)

    high_feats = [_extract_features(p) for p in groups["high"]]
    normal_feats = [_extract_features(p) for p in groups["normal"]]

    dimensions = {}
    for dim, key, kind in [
        ("topic", "topic", "categorical"),
        ("hook", "hook_question", "bool"),
        ("structure", "structure_list", "bool"),
        ("information_density", "info_density_digits", "numeric"),
        ("cta", "cta_present", "bool"),
        ("interaction", "interaction_hashtags", "numeric"),
    ]:
        if kind == "numeric":
            hi = [f[key] for f in high_feats]
            no = [f[key] for f in normal_feats]
            hi_avg = round(sum(hi) / len(hi), 2) if hi else 0
            no_avg = round(sum(no) / len(no), 2) if no else 0
            diff = round(hi_avg - no_avg, 2)
        else:
            hi = sum(1 for f in high_feats if f[key])
            no = sum(1 for f in normal_feats if f[key])
            hi_rate = round(hi / len(high_feats), 2) if high_feats else 0
            no_rate = round(no / len(normal_feats), 2) if normal_feats else 0
            diff = round(hi_rate - no_rate, 2)
            hi_avg, no_avg = hi_rate, no_rate

        # Evidence level:
        #   OBSERVED = directly measurable feature difference (always true for
        #              the feature values we compute).
        #   INFERRED = the claim that this feature *drives* performance.
        #   UNKNOWN  = cannot judge when either group is empty / too small.
        if not high_feats or not normal_feats:
            evidence = "UNKNOWN"
            note = "insufficient data to compare groups"
        else:
            evidence = "OBSERVED"
            note = "feature difference is directly observed; causality not proven"
        dimensions[dim] = {
            "high": hi_avg,
            "normal": no_avg,
            "diff": diff,
            "observed_level": evidence,
            "inferred_driver": None if diff == 0 else (
                f"high-performing content shows {'more' if diff > 0 else 'fewer'} {dim} signals "
                "(INFERRED driver; correlation, not causation)"
            ),
            "unknown_reason": note if evidence == "UNKNOWN" else "",
        }

    return {
        "account": posts[0].get("account", "") if posts else "",
        "data_authenticity": posts[0].get("data_authenticity", "") if posts else "",
        "group_threshold": groups.get("threshold"),
        "high_count": len(groups["high"]),
        "normal_count": len(groups["normal"]),
        "high_posts": groups["high"],
        "normal_posts": groups["normal"],
        "dimensions": dimensions,
        "evidence_legend": {
            "OBSERVED": "直接观察到的特征差异（不代表因果）",
            "INFERRED": "推测的可能驱动因素（相关性≠因果）",
            "UNKNOWN": "当前数据无法证明",
        },
    }


def structure_templates(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Distill reusable structure templates from observed dimensions."""
    dims = result.get("dimensions", {})
    templates = []
    hooks = []
    if dims.get("hook", {}).get("diff", 0) > 0:
        hooks.append("question or strong opener")
    if dims.get("information_density", {}).get("diff", 0) > 0:
        hooks.append("lead with a concrete number")
    if dims.get("cta", {}).get("diff", 0) > 0:
        hooks.append("end with an explicit CTA question")
    if dims.get("structure", {}).get("diff", 0) > 0:
        hooks.append("use list/numbered structure")

    if hooks:
        templates.append(
            {
                "name": "Finimize-style high-engagement template",
                "elements": hooks,
                "evidence_level": "INFERRED",
                "note": "correlation not causation; derived from observed feature differences",
                "source_account": result.get("account", ""),
            }
        )
    return templates

"""Content safety & financial risk check.

Deterministic rules produce a risk level (LOW / MEDIUM / HIGH) with an
explainable list of hit signals and evidence snippets.

Trigger rules (per content-safety spec):
  HIGH (Blocked): guaranteed return, deterministic price prediction,
                  direct stock/investment advice, sensitive-region issue.
  MEDIUM (revise + re-check): unverified claims, unsourced factual statements,
                  high similarity to benchmark, plagiarism-style phrasing.
  LOW (human review, no auto-approve): none of the above.
"""
from typing import Any, Dict, List

from core import config

HIGH_PATTERNS = {
    "guaranteed_return": (
        "guaranteed return", "guaranteed profit", "risk-free", "risk free",
        "sure win", "guaranteed", "no risk", "guaranteed to",
    ),
    "deterministic_price_prediction": (
        "will rise to", "will fall to", "will reach", "will hit", "will go up",
        "will go down", "definitely", "certainly", "price will", "will surge",
        "will crash", "is going to", "target price of",
    ),
    "direct_investment_advice": (
        "buy now", "sell now", "should buy", "should sell", "must buy",
        "invest now", "buy the dip", "all in", "go long", "go short",
        "load up on", "dump your", "should invest",
    ),
    "sensitive_region": (
        # sensitive-region issues — kept generic to avoid false negatives on
        # content that frames geopolitical topics as investment calls
        "taiwan independence", "separatist", "territorial dispute",
    ),
}

MEDIUM_PATTERNS = {
    "unverified_claim": (
        "rumor", "rumour", "reportedly", "allegedly", "sources say",
        "unconfirmed", "unverified", "anonymous sources", "hearsay",
    ),
    "unsourced_factual": (),
    # unsourced factual statements are detected structurally (digits w/o URL)
    "high_similarity": (),  # set via TF-IDF similarity, not keyword
    "plagiarism_phrasing": (),  # set via continuous-phrase match, not keyword
}


def _has(tokens, text_lower):
    return [t for t in tokens if t in text_lower]


def _contains_digits_without_source(body: str) -> bool:
    import re

    has_digits = bool(re.search(r"\b\d+(\.\d+)?%?\b", body))
    has_source = bool(re.search(r"(source:|来源|http://|https://|reuters|bloomberg|per )", body, re.I))
    return has_digits and not has_source


def check_content(body: str, similarity_score: float = 0.0, benchmark_hit: str = "") -> Dict[str, Any]:
    """Return {risk_level, signals, evidence, advice}."""
    lower = body.lower()
    signals: List[Dict[str, Any]] = []

    # HIGH signals
    for label, tokens in HIGH_PATTERNS.items():
        hits = _has(tokens, lower)
        if hits:
            signals.append({"signal": label, "level": "HIGH", "evidence": hits[:3]})

    # MEDIUM keyword signals
    for label, tokens in MEDIUM_PATTERNS.items():
        if not tokens:
            continue
        hits = _has(tokens, lower)
        if hits:
            signals.append({"signal": label, "level": "MEDIUM", "evidence": hits[:3]})

    # unsourced factual statements (structural)
    if _contains_digits_without_source(body):
        signals.append(
            {"signal": "unsourced_factual", "level": "MEDIUM", "evidence": ["digits present without a source"]}
        )

    # similarity / plagiarism (from TF-IDF cosine)
    if similarity_score >= config.SIMILARITY_THRESHOLD:
        signals.append(
            {
                "signal": "high_similarity",
                "level": "MEDIUM",
                "evidence": [f"cosine similarity {similarity_score:.3f} vs {benchmark_hit or 'benchmark'}"],
            }
        )

    # aggregate
    if any(s["level"] == "HIGH" for s in signals):
        level = "HIGH"
        advice = "Blocked: contains guaranteed-return / price-prediction / investment-advice / sensitive content."
    elif signals:
        level = "MEDIUM"
        advice = "Revise and re-check before review."
    else:
        level = "LOW"
        advice = "Allowed into human review; no auto-approve."

    return {
        "risk_level": level,
        "signals": signals,
        "evidence": [s["evidence"] for s in signals],
        "advice": advice,
    }


def check_candidate(candidate: Dict[str, Any], similarity_score: float = 0.0, benchmark_hit: str = "") -> Dict[str, Any]:
    """Check a candidate dict (has body_en) and attach risk result.

    If the candidate carries fact_sources, the digits are treated as sourced
    (the source lives in the candidate metadata, not necessarily inline).
    """
    body = candidate.get("body_en", "")
    has_sources = bool(candidate.get("fact_sources"))
    # append a source marker so _contains_digits_without_source is satisfied
    if has_sources:
        body = body + "\nSource: " + ", ".join(str(s) for s in candidate["fact_sources"][:1])
    result = check_content(body, similarity_score, benchmark_hit)
    candidate["risk_level"] = result["risk_level"]
    candidate["risk_signals"] = result["signals"]
    candidate["risk_advice"] = result["advice"]
    return result

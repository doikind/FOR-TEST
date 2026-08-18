"""Follow decision: follow / consider / caution / skip, driven by the brand
account profile (core.account) — "is this worth OUR account following?"

Deterministic rule engine (no model). Combines:
  1. risk / low-value patterns (caution / skip)
  2. brand relevance (core.account.relevance_score)
  3. priority score
Output includes relevance details for explainability.
"""
from core.account import relevance_score

CAUTION_TOKENS = (
    "fraud", "lawsuit", "sue", "sued", "scandal", "scam", "hack", "hacked",
    "breach", "crash", "collapse", "bankrupt", "manipulation", "recall",
    "death", "killed", "terror", "war", "sanction", "crisis", "bubble",
    "reckoning", "plunge", "selloff", "meltdown", "warning", "warns",
    "hallucination", "governance gap", "examination risk", "downgrade",
)

SKIP_TOKENS = (
    "job", "jobs", "hiring", "career", "careers", "salary", "appoint",
    "appointed", "appoints", "leadership", "promotion", "recruit", "internship",
    "sponsored", "advertorial", "press release", "how to", "guide", "review",
    "top 10", "list of", "quiz",
)

PROMO_PATTERNS = ("deal", "discount", "coupon", "sale", "promo", "free trial")


def decide(ev) -> tuple[str, list[str], dict]:
    """Return (decision, reasons, relevance_info).

    relevance_info = {score, topics, regions, reasons} from core.account.
    """
    title = (ev.title or "").lower()
    reasons = []
    rel = relevance_score(ev)
    relevance = rel["score"]
    category = ev.category or "general"
    priority = ev.priority_score or 0.0

    # 1. caution: risk / negative-market signals (regardless of relevance)
    if any(tok in title for tok in CAUTION_TOKENS):
        reasons.append("命中风险/负面市场信号，需先做风险核查")
        return "caution", reasons, rel

    # 2. skip: jobs / promotions / low-value content patterns
    if any(tok in title for tok in SKIP_TOKENS):
        reasons.append("命中招聘/促销/低价值模式")
        return "skip", reasons, rel
    if any(p in title for p in PROMO_PATTERNS):
        reasons.append("促销内容")
        return "skip", reasons, rel

    # 3. brand relevance + priority → follow / consider / skip
    #    Hacker News items are community-shared links (often personal blogs),
    #    NOT official news — they never get 'follow' directly.
    is_hn = (ev.source_category or "") == "hacker_news" or "hacker" in (ev.source or "").lower()
    if relevance >= 0.7:
        if priority >= 0.6 and not is_hn:
            reasons.append(f"高相关(relevance={relevance})且高优先级({priority:.2f})，值得跟进")
            return "follow", reasons, rel
        if is_hn:
            reasons.append(f"高相关(relevance={relevance})，但来源为 Hacker News 社区分享（非官方媒体），建议核实后再跟进")
            return "consider", reasons, rel
        reasons.append(f"高相关(relevance={relevance})但优先级中等({priority:.2f})，可考虑")
        return "consider", reasons, rel
    if relevance >= 0.4:
        reasons.append(f"中等相关(relevance={relevance})，按优先级({priority:.2f})酌情考虑")
        return "consider", reasons, rel
    reasons.append(f"相关性低(relevance={relevance})，不值得我方账号跟进")
    return "skip", reasons, rel


def annotate(events) -> None:
    """Set follow_decision + relevance + follow_reasons on each event in place."""
    for ev in events:
        decision, reasons, rel = decide(ev)
        ev.follow_decision = decision
        ev.priority_reasons["follow_reasons"] = reasons
        ev.priority_reasons["relevance"] = rel

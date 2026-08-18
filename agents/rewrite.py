"""Original rewrite engine — turns an insight (source post text) into
ORIGINAL candidate posts, never copying the source verbatim.

Design (deterministic, key-free, no LLM dependency):
  1. Extract KEY FACTS from the insight: numbers, proper nouns, domain terms.
     Full source sentences are discarded — only atoms survive.
  2. Each candidate is built by combining a fact-driven HOOK (that quotes the
     extracted number/noun), an insight LENS (builder/investor/product/...),
     and a CTA — drawn from large pools so no two candidates share the same
     sentence pattern. The lead fact rotates per candidate.
  3. Output is a genuine rewrite: same facts, different words, natural voice.
"""

import random
import re
from typing import Dict, List, Tuple

_NUM_RE = re.compile(r"\$[\d,]+(?:\.\d+)?[MBK]?|\d+(?:\.\d+)?%?|[\d.,]+x")
_NOUN_RE = re.compile(r"\b(?:[A-Z][a-z]{2,}\s*){1,3}\b")
_DOMAIN_NOUNS = ("ETF", "ETFs", "AI stocks", "earnings season", "beat rate",
                 "tech stocks", "yield", "inflation", "margin", "valuation",
                 "cash flow", "interest rate", "bank", "fintech", "stablecoin",
                 "blockchain", "Crypto", "equity", "bonds", "AI", "IPO")

_WORD_STOP = {"the", "this", "that", "week", "today", "what", "your", "its",
              "and", "but", "for", "with", "from", "are", "will", "would"}

# Fact-driven hooks (quote the extracted number/noun — never generic filler).
_HOOKS_NUM = [
    "{num} — that's the figure quietly doing the work in the {topic} story.",
    "A {num} move in {topic} barely registered. It should have.",
    "The number behind the {topic} coverage: {num}.",
    "Nobody is quoting this one: {num}, in the {topic} trend.",
    "{num}. That's the {topic} signal that keeps getting skipped.",
]
_HOOKS_NUM_ONLY = [
    "{num}. That number deserves more than a passing mention.",
    "Read this number twice: {num}.",
    "The figure that matters most this week isn't the one in the headline — it's {num}.",
    "{num} is the datapoint that re-frames the story.",
]
_HOOKS_NO_NUM = [
    "The {topic} story is moving faster than the coverage suggests.",
    "Most feeds are showing one side of the {topic} story.",
    "Here's the {topic} angle that's getting buried this week.",
    "The {topic} story has a second chapter nobody's telling.",
    "Everyone circled the {topic} headline. The detail matters more.",
]
_HOOKS_BARE = [
    "One datapoint this week didn't get the attention it deserved.",
    "The most interesting market signal this week wasn't in a headline.",
    "A quiet shift in the data says more than the loud takes do.",
]
# Question-style hooks (used when the breakdown shows question hooks perform well).
_HOOKS_QUESTION = [
    "What changed in {topic} that most feeds haven't priced in yet?",
    "Is {topic} the signal everyone's about to miss, or the noise they should skip?",
    "Why is {topic} moving faster than the coverage suggests?",
    "Here's the question behind {topic} that nobody's asking.",
    "How much of {topic} is already priced in — and how much isn't?",
]

# Context — expands the fact into the bigger picture (2-3 lines).
_CONTEXT = [
    "Here's the context: {topic} didn't happen in isolation. It sits on a longer trend that's been building quietly for quarters.",
    "Put it in perspective: the {topic} move matters less on its own than in what it says about the direction of travel.",
    "Context matters — {topic} is one quarter, but the pattern behind it has been consistent for a while now.",
    "The headline captures the event. The context around {topic} captures the trajectory.",
    "Zoom out for a second: the {topic} datapoint is really a tell about where the cycle is headed.",
]

# Insight — the real point being made (weaves the fact).
_INSIGHT = [
    "The insight: when {topic} shows up with numbers like this, it's usually the leading indicator — not the lagging one.",
    "The part most people miss: this reframes how {topic} gets priced, not just this quarter but the quarters after.",
    "What it actually tells us: the gap between the {topic} story and the data is where the opportunity sits.",
    "The read: if the {topic} trend holds, the next set of forecasts will look stale within a quarter.",
    "The deeper point: markets price {topic} narratives first and reconcile with data later — this is data arriving early.",
]

# Uncomfortable truth — the insight most people avoid.
_TRUTHS = [
    "The uncomfortable truth: most of the commentary around {topic} is already priced in — the real signal is what nobody's modeling.",
    "Uncomfortable truth: the consensus is treating {topic} as an event, but it's structural.",
    "Here's the part nobody wants to say: the easy reaction trade on {topic} is obvious, which is exactly why it's crowded.",
    "The uncomfortable part: the {topic} data is ahead of the narrative, and the narrative usually wins short-term.",
    "Truth most people skip: {topic} momentum compounds until it doesn't — timing the turn is harder than spotting it.",
]

# Payoffs — a close that lands the point.
_PAYOFFS = [
    "Worth it to follow {topic}? The signal says yes — what changes is the timeline, not the direction.",
    "Bottom line: the {topic} datapoint is worth saving, because it'll matter more in six months than it does today.",
    "That's the throughline: attention follows the {topic} headline, but allocation follows the data.",
    "The payoff: get {topic} right now, and the next quarter reads like an obvious continuation.",
    "If you take one thing from this: the {topic} move is real, the debate is about speed — and speed is where edge lives.",
]

# Number line — anchors the post to a concrete figure from the source,
# so the rewrite is data-driven, not just topic-driven.
_NUMBER_LINES = [
    "The figure to anchor on: {num}, in the {topic} story.",
    "Concretely: {num} — that's the number doing the work behind {topic}.",
    "For scale, look at {num} — the datapoint that makes {topic} matter.",
    "Put a number on it: {num}, and what it implies for {topic}.",
    "The key metric here is {num}, sitting right at the center of {topic}.",
]

# CTAs — varied, natural, anchored to the topic.
_CTAS = [
    "What would change your read on {topic}?",
    "Where do you see the second-order effect in {topic} first?",
    "Is the {topic} signal or noise to you?",
    "Curious how you're weighting {topic}.",
    "Does {topic} change your view of the sector?",
    "Who's most exposed if {topic} keeps compounding?",
]

# angle pairs: (EN label, ZH label) — same index, always in sync
_ANGLE_PAIRS = [
    ("data-first lens", "数据先行视角：以具体数字/指标切入"),
    ("investor lens", "投资者视角：从仓位/定价/二阶效应切入"),
    ("contrarian lens", "反共识视角：挑战主流解读"),
    ("builder lens", "构建者视角：从基础设施/产品落地切入"),
    ("second-order lens", "二阶效应视角：关注数据驱动的连锁影响"),
]


def _strip_entities(s: str) -> str:
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"[\U0001F300-\U0001FAFF]", "", s)
    s = re.sub(r"[#@]\w+", "", s)
    return s


def extract_facts(insight: str) -> Tuple[List[str], List[str]]:
    """Return (numbers, noun_phrases) extracted from the insight. Atoms only."""
    cleaned = _strip_entities(insight)
    numbers = _NUM_RE.findall(cleaned)
    nouns = []
    for m in _NOUN_RE.finditer(cleaned):
        phrase = m.group(0).strip()
        tokens = phrase.split()
        while tokens and tokens[0].lower() in _WORD_STOP:
            tokens = tokens[1:]
        while tokens and tokens[-1].lower() in _WORD_STOP:
            tokens = tokens[:-1]
        phrase = " ".join(tokens)
        if len(phrase.split()) >= 2 and len(phrase) <= 40:
            nouns.append(phrase)
    lower = cleaned.lower()
    for dn in _DOMAIN_NOUNS:
        if dn.lower() in lower:
            nouns.append(dn)
    # ticker mentions like $FN / $DELL / $NVDA are strong facts
    for m in re.finditer(r"\$([A-Z]{1,5})\b", cleaned):
        nouns.append(m.group(1))
    seen, uniq_n = set(), []
    for n in nouns:
        key = n.lower()
        if key.endswith("s") and key[:-1] in seen:
            continue
        if key in seen:
            continue
        seen.add(key)
        uniq_n.append(n)
    uniq_num = [n.rstrip(",.") for n in dict.fromkeys(numbers)]
    # prioritize money / percent / multiples over plain years
    def _rank(num: str) -> int:
        if num.startswith("$"):
            return 0
        if num.endswith("%"):
            return 1
        if num.endswith("x"):
            return 2
        if num.isdigit() and len(num) == 4:  # years last
            return 3
        return 2
    uniq_num.sort(key=_rank)
    return uniq_num[:6], uniq_n[:6]


def extract_topic(insight: str) -> str:
    """Extract a compact topic phrase that anchors the rewrite to THIS content.

    Strategy: prefer 'ticker + short theme' (e.g. '$FN earnings'); then a
    proper-noun phrase; then a short noun head. Filtered to 2-4 content words,
    skipping earnings-format filler (revenue, quarter, fiscal, compared, etc.).
    """
    cleaned = _strip_entities(insight)
    # strip retweet prefixes (with or without @) so the topic is the content
    cleaned = re.sub(
        r"^(?:rt by|r to|retweet)\b[^:]{0,30}?:\s*|^(?:rt by|r to|retweet)\s+",
        "", cleaned, flags=re.I,
    ).lstrip()

    _FILLER = {"earnings", "revenue", "quarter", "fiscal", "compared", "million",
               "billion", "year", "results", "reported", "announced", "record",
               "increase", "decrease", "fourth", "third", "second", "first",
               "were", "was", "been", "have", "has", "from", "for", "the",
               "of", "in", "on", "at", "to", "with", "and"}

    def _content_words(text: str, limit: int) -> List[str]:
        words = [re.sub(r"[^A-Za-z0-9]", "", w) for w in text.split()]
        # drop pure numbers (years/amounts) — those are 'facts', not topic words
        words = [w for w in words if not w.isdigit()]
        kept = []
        for w in words:
            if not w or w.lower() in _WORD_STOP or w.lower() in _FILLER:
                continue
            # avoid repeated adjacent words ('story story')
            if kept and kept[-1].lower() == w.lower():
                continue
            kept.append(w)
        return kept[:limit]

    # 1. ticker-led theme: '$XXX' + up to ~3 following content words
    m = re.search(r"\$([A-Z]{1,5})\b\s*([^,.\n!?]{0,60})", cleaned)
    if m:
        ticker = m.group(1)
        rest_words = _content_words(m.group(2), 3)
        phrase = " ".join([ticker] + rest_words)
        if len(phrase.split()) >= 2:
            return phrase[:50]

    # 2. proper-noun phrase (2-3 words)
    nouns = _NOUN_RE.findall(cleaned)
    if nouns:
        toks = _content_words(nouns[0], 3)
        if len(toks) >= 2:
            return " ".join(toks)

    # 3. short head of first sentence (max 4 words)
    sent = re.split(r"[.!?]", cleaned)[0]
    toks = _content_words(sent, 4)
    if toks:
        return " ".join(toks)
    return "this development"


def _pick_hook(nums: List[str], topic: str, i: int,
               hooks_num, hooks_nonum, hooks_num_only, hooks_bare,
               hooks_question, style: Dict[str, bool]) -> str:
    if style.get("hook_question"):
        return hooks_question[i % len(hooks_question)].format(topic=topic)
    if style.get("number_first") and nums:
        lead_num = nums[i % len(nums)]
        return hooks_num_only[i % len(hooks_num_only)].format(num=lead_num)
    if nums:
        lead_num = nums[i % len(nums)]
        return hooks_num[i % len(hooks_num)].format(num=lead_num, topic=topic)
    if topic:
        return hooks_nonum[i % len(hooks_nonum)].format(topic=topic)
    return hooks_bare[i % len(hooks_bare)]


def generate_original_posts(insight: str, n: int = 3, style: Dict[str, bool] | None = None) -> List[Dict[str, str]]:
    """Return n original post drafts as genuine rewrites of the insight.

    style (from a viral breakdown) drives the post structure:
      hook_question=True → question-style hook
      number_first=True  → lead with the concrete number
      cta_question=True  → CTA is a question (pools already are)
    When style is None, behavior is the previous generic-random selection.

    Five-part structure (inspired by X thread/long-form writing skills):
      Hook (stop-the-scroll, fact-driven)
      Context (bigger picture, 1-2 lines)
      Insight (the real point, weaving the fact)
      Uncomfortable truth (what most people avoid)
      Payoff + CTA (land the point, invite reply)

    Every paragraph anchors to the extracted TOPIC of THIS content, so the
    rewrite stays closely related — not a generic filler post.

    Deterministic per insight (seed from hash) but every candidate differs:
    lead fact rotates, each section draws from a shuffled pool with offsets.
    """
    nums, nouns = extract_facts(insight)
    topic = extract_topic(insight)
    style = style or {}
    rng = random.Random(hash(insight) & 0xFFFFFFFF)
    hooks_num = _HOOKS_NUM[:]; rng.shuffle(hooks_num)
    hooks_nonum = _HOOKS_NO_NUM[:]; rng.shuffle(hooks_nonum)
    hooks_num_only = _HOOKS_NUM_ONLY[:]; rng.shuffle(hooks_num_only)
    hooks_bare = _HOOKS_BARE[:]; rng.shuffle(hooks_bare)
    hooks_question = _HOOKS_QUESTION[:]; rng.shuffle(hooks_question)
    contexts = _CONTEXT[:]; rng.shuffle(contexts)
    insights = _INSIGHT[:]; rng.shuffle(insights)
    truths = _TRUTHS[:]; rng.shuffle(truths)
    payoffs = _PAYOFFS[:]; rng.shuffle(payoffs)
    ctas = _CTAS[:]; rng.shuffle(ctas)
    angles = _ANGLE_PAIRS[:]; rng.shuffle(angles)
    number_lines = _NUMBER_LINES[:]; rng.shuffle(number_lines)

    posts = []
    for i in range(n):
        hook = _pick_hook(nums, topic, i, hooks_num, hooks_nonum, hooks_num_only, hooks_bare,
                          hooks_question, style)
        # context/insight/truth/payoff pick different pool offsets per candidate
        ctx = contexts[i % len(contexts)].format(topic=topic)
        ins = insights[(i + 1) % len(insights)].format(topic=topic)
        truth = truths[(i + 2) % len(truths)].format(topic=topic)
        payoff = payoffs[(i + 3) % len(payoffs)].format(topic=topic)
        cta = ctas[(i + 4) % len(ctas)].format(topic=topic)
        angle_en, angle_zh = angles[i % len(angles)]

        # weave a concrete number from the source into every post (data-driven)
        num_line = ""
        if nums:
            lead_num = nums[i % len(nums)]
            num_line = number_lines[i % len(number_lines)].format(num=lead_num, topic=topic)

        body_lines = [hook, "", ctx]
        if num_line:
            body_lines.append(num_line)
        body_lines += ["", ins, "", truth, payoff, cta]
        posts.append(
            {
                "angle_en": f"Original rewrite #{i+1} ({angle_en})",
                "angle_zh": f"选题角度 {i+1}：{angle_zh}（主题：{topic}）",
                "body_en": "\n".join(body_lines),
                "cta": cta,
                "hook_style": angle_en,
                "topic": topic,
                "facts_used": {"numbers": nums, "nouns": nouns},
            }
        )
    return posts

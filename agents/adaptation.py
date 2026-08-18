"""Agent 1 content adaptation — turn a hot-topic headline into an ORIGINAL
publishable X post without copying the source sentence.

Approach (deterministic, key-free, adapted from content-rewrite skill patterns):
  1. Extract a CLEAN topic (entities + translated keywords) from the title —
     never a raw headline fragment.
  2. Extract key facts (numbers / tickers / entities).
  3. Compose a post with distinct structure per variant:
     Hook (question/stat) → Fact (paraphrased, with the key number/ticker)
     → Angle (investor/builder/contrarian) → CTA.
No source sentence is kept verbatim; similarity vs source is re-checked by
the pipeline's TF-IDF.
"""
import random
import re
from typing import Dict, List

from agents import zh_support

# Adaptation structures — each variant re-orders and re-words the facts.
_HOOKS = [
    "Here's a market move worth your attention: {topic}.",
    "Most timelines will scroll past this — {topic} deserves a closer look.",
    "The story under the radar today: {topic}.",
    "Worth reading on {topic}: the numbers tell a different story than the headline.",
]
_FACTS = [
    "The key datapoint: {fact}. That's the signal, not the noise.",
    "Look at the substance: {fact}. This is what the coverage is missing.",
    "Underneath it: {fact}. The implication is bigger than the announcement.",
]
_ANGLES = [
    "For investors, this shifts how {topic} gets priced over the next quarters.",
    "For builders, this changes the default assumption in {topic}.",
    "The second-order effect in {topic} is where the real opportunity sits.",
]
_CTAS = [
    "What's your read — signal or noise?",
    "How are you weighting this one?",
    "Where do you see the impact first?",
]


def _clean_topic(title: str) -> str:
    """Clean ENGLISH topic for the post body: entities + content words,
    never a raw truncated fragment and never Chinese gloss (ZH is for notes)."""
    body = title.split(" - ")[0]
    # entities (capitalized runs) — keep only clearly proper nouns, cap at 2
    entities = re.findall(r"\b([A-Z][A-Za-z]{2,})\b", body)
    entities = [e for e in entities if e.lower() not in
                {"the", "and", "mas", "announces", "rules", "for", "bank", "card",
                 "credit", "cashback", "rewards", "with", "launches", "new"}]
    # content keywords (lowercase common financial terms)
    keywords = re.findall(r"\b(digital|fintech|bank|banking|licensing|finance|investing|ai|crypto|market|funding|payment)\b", body.lower())
    toks = []
    seen = set()
    for e in entities[:2] + keywords:
        k = e.lower()
        if k not in seen:
            seen.add(k)
            toks.append(e if e[0].isupper() else e.lower())
    return " ".join(toks[:5]) if toks else body[:30]


def _facts(title: str) -> List[str]:
    """Short factual atoms extracted from the title (not full sentences).

    Keeps only: numbers/percent/money + tickers + proper-noun pairs where
    BOTH words are real entities (not common capitalized words).
    """
    facts = []
    for m in re.finditer(r"\$[A-Z]{1,5}\b|\d+(?:\.\d+)?%?|\$[\d,]+(?:\.\d+)?[MBK]?", title):
        facts.append(m.group(0))
    _COMMON = {"bank", "card", "credit", "with", "launches", "cashback", "rewards",
               "the", "and", "for", "new", "rules", "announces"}
    for m in re.finditer(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b", title):
        w1, w2 = m.group(1), m.group(2)
        if w1.lower() in _COMMON or w2.lower() in _COMMON:
            continue
        facts.append(f"{w1} {w2}")
    return list(dict.fromkeys(facts))[:3]


def _fact_str(title: str) -> str:
    facts = _facts(title)
    topic = _clean_topic(title)
    return ", ".join(facts) if facts else topic


def adapt_publish_text(title: str, source: str = "", n: int = 3) -> List[Dict[str, str]]:
    """Produce n adapted publishable posts for one headline."""
    topic = _clean_topic(title)
    fact = _fact_str(title)

    rng = random.Random(hash(title) & 0xFFFFFFFF)
    hooks = _HOOKS[:]; rng.shuffle(hooks)
    fact_lines = _FACTS[:]; rng.shuffle(fact_lines)
    angles = _ANGLES[:]; rng.shuffle(angles)
    ctas = _CTAS[:]; rng.shuffle(ctas)

    posts = []
    for i in range(n):
        hook = hooks[i % len(hooks)].format(topic=topic)
        fact_line = fact_lines[(i + 1) % len(fact_lines)].format(fact=fact)
        angle = angles[(i + 2) % len(angles)].format(topic=topic)
        cta = ctas[(i + 3) % len(ctas)]
        src_note = f"\nSource: {source}" if source else ""
        body = f"{hook}\n\n{fact_line}\n\n{angle}\n\n{cta}{src_note}\n\nThis content is for informational purposes only and does not constitute investment advice."
        posts.append(
            {
                "angle_en": f"Adapted variant #{i+1}",
                "angle_zh": f"改编变体 #{i+1}（主题：{topic}）",
                "body_en": body,
                "cta": cta,
                "topic": topic,
                "facts_used": _facts(title),
            }
        )
    return posts


def adapt_one(title: str, source: str = "") -> Dict[str, str]:
    """Single adapted post (default pool for the pool page)."""
    return adapt_publish_text(title, source, n=1)[0]

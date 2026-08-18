"""Event summary & content-angle generation, backed by the AI provider.

For a chosen event this produces bilingual output:
  - English summary (X content) + Chinese summary (internal review)
  - suggested content angles, English (provider) + Chinese (topic-anchored)
  - Chinese headline translation + keywords for quick browsing
"""
from typing import Any, Dict, List

from agents import zh_support
from agents.ai_provider import get_provider
from core.models import Event


def summarize_event(event: Event) -> str:
    return get_provider().summarize(event)


def summarize_event_zh(event: Event) -> str:
    return get_provider().summarize_zh(event)


def suggest_angles(event: Event, n: int = 3) -> List[str]:
    return get_provider().suggest_angles(event, n=n)


def suggest_angles_zh(event: Event, n: int = 3) -> List[str]:
    return get_provider().suggest_angles_zh(event, n=n)


def enrich_event(event: Event) -> Dict[str, Any]:
    """Attach bilingual summary + angles + Chinese title/keywords to an event.

    Chinese angles are anchored to THIS post's topic + keywords (precise),
    while the English angles come from the provider template.
    """
    event.summary = summarize_event(event)
    event.angles = suggest_angles(event)
    d = event.to_dict()
    d["summary_zh"] = summarize_event_zh(event)
    # precise Chinese support: title translation, topic, keywords, angles
    zh = zh_support.enrich_zh(event.title)
    d["title_zh"] = zh["title_zh"]
    d["topic_zh"] = zh["topic_zh"]
    d["keywords_zh"] = zh["keywords_zh"]
    d["angles_zh"] = zh["angles_zh"]
    # Chinese event summary (deterministic, for hot-topic tracking)
    d["summary_zh_text"] = zh_support.summarize_zh(event.title, event.source, event.category)
    return d

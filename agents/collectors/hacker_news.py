"""Hacker News collector — AI/tech & developer discussion signal."""
import datetime as dt
import json
import urllib.request
from typing import List

from agents.collectors.base import CollectResult, SourceWarning, make_ua
from core.authenticity import LIVE_PUBLIC
from core.models import Event

TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

# Stories whose title hints at the brand's domain (AI / fintech / investing / startup).
TOPIC_TOKENS = (
    "ai", "artificial", "llm", "model", "openai", "anthropic", "ml",
    "fintech", "finance", "bank", "payment", "invest", "fund", "crypto",
    "startup", "vc", "funding", "market", "stock", "trading",
)


def _is_relevant(title: str) -> bool:
    t = title.lower()
    return any(tok in t for tok in TOPIC_TOKENS)


def collect(limit: int = 10) -> CollectResult:
    result = CollectResult()
    collected_at = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        req = urllib.request.Request(TOP_STORIES_URL, headers={"User-Agent": make_ua()})
        with urllib.request.urlopen(req, timeout=25) as resp:
            ids = json.load(resp)
    except Exception as e:  # noqa: BLE001
        result.warnings.append(SourceWarning("Hacker News", f"{type(e).__name__}: {e}"))
        return result

    fetched = 0
    for story_id in ids:
        if fetched >= limit:
            break
        try:
            req = urllib.request.Request(ITEM_URL.format(id=story_id), headers={"User-Agent": make_ua()})
            with urllib.request.urlopen(req, timeout=15) as resp:
                item = json.load(resp)
        except Exception:  # noqa: BLE001
            continue
        if not item or item.get("type") != "story":
            continue
        title = (item.get("title") or "").strip()
        url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('id')}"
        if not title or not _is_relevant(title):
            continue
        ts = item.get("time")
        published_at = ""
        if ts:
            try:
                published_at = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).isoformat()
            except Exception:  # noqa: BLE001
                published_at = ""
        result.events.append(
            Event(
                title=title,
                source="Hacker News",
                url=url,
                published_at=published_at,
                collected_at=collected_at,
                source_category="hacker_news",
                data_authenticity=LIVE_PUBLIC,
                heat_score=float(item.get("score") or 0),
            )
        )
        fetched += 1
    return result

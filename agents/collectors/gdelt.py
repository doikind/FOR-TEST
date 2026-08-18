"""GDELT collector — news coverage & regional cross-validation.

Uses the free GDELT 2.0 DOC API (no key). Note: the public endpoint is
rate-limited (429) and may be intermittently unavailable; failures are
reported as warnings, never as fabricated news.
"""
import datetime as dt
import json
import urllib.parse
import urllib.request
from typing import List

from agents.collectors.base import CollectResult, SourceWarning, make_ua
from core.authenticity import LIVE_PUBLIC
from core.models import Event

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def collect(query: str = "fintech OR (artificial intelligence finance)", maxrecords: int = 20) -> CollectResult:
    result = CollectResult()
    collected_at = dt.datetime.now(dt.timezone.utc).isoformat()
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": str(maxrecords),
        "format": "json",
        "timespan": "2d",
        "sort": "hybridrel",
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": make_ua()})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except Exception as e:  # noqa: BLE001
        result.warnings.append(SourceWarning("GDELT", f"{type(e).__name__}: {e}"))
        return result

    articles = data.get("articles", []) if isinstance(data, dict) else []
    seen = set()
    for a in articles:
        title = (a.get("title") or "").strip()
        url = (a.get("url") or "").strip()
        if not title or not url or url in seen:
            continue
        seen.add(url)
        # seendate is YYYYMMDDTHHMMSSZ
        published_at = ""
        sd = a.get("seendate") or ""
        if len(sd) >= 8:
            try:
                published_at = dt.datetime.strptime(sd[:8], "%Y%m%d").replace(
                    tzinfo=dt.timezone.utc
                ).isoformat()
            except Exception:  # noqa: BLE001
                published_at = ""
        result.events.append(
            Event(
                title=title,
                source="GDELT",
                url=url,
                published_at=published_at,
                collected_at=collected_at,
                source_category="gdelt",
                data_authenticity=LIVE_PUBLIC,
            )
        )
    return result

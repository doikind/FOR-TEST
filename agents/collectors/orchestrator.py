"""Collection orchestrator — runs each source independently, degrades gracefully."""
import datetime as dt
from typing import List

from agents.collectors import gdelt, google_news, hacker_news
from agents.collectors.base import CollectResult, SourceWarning
from core import config
from core.models import Event


def collect_all() -> CollectResult:
    """Run all enabled collectors; single-source failure never aborts the rest."""
    result = CollectResult()

    def _safe(name: str, fn) -> None:
        try:
            r = fn()
            result.events.extend(r.events)
            result.warnings.extend(r.warnings)
        except Exception as e:  # noqa: BLE001 — collector-level failure degrades
            result.warnings.append(SourceWarning(name, f"{type(e).__name__}: {e}"))

    if config.SOURCE_GOOGLE_NEWS:
        _safe("Google News", google_news.collect)
    if config.SOURCE_GDELT:
        _safe("GDELT", gdelt.collect)
    if config.SOURCE_HACKER_NEWS:
        _safe("Hacker News", hacker_news.collect)
    if config.SOURCE_COINGECKO:
        from agents.collectors import coingecko

        _safe("CoinGecko", coingecko.collect)

    return result


def collect_summary() -> dict:
    """Collect and return a JSON-safe summary (counts + warnings) for UI/CLI."""
    result = collect_all()
    by_source = {}
    for ev in result.events:
        by_source[ev.source_category] = by_source.get(ev.source_category, 0) + 1
    return {
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "total_events": len(result.events),
        "by_source": by_source,
        "warnings": [{"source": w.source, "reason": w.reason} for w in result.warnings],
        "events": [ev.to_dict() for ev in result.events],
    }

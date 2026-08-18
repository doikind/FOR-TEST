"""Snapshot generation & loading — real public data, cached_public labeled.

Snapshots are produced ONLY by collecting from the real public interfaces
(never hand-written). They preserve source URL, published_at and
collected_at, and are labeled cached_public. Loading a snapshot must never
silently present as live data.
"""
import datetime as dt
import json
import os
from typing import List

from core import config
from core.authenticity import CACHED_PUBLIC
from core.models import Event


def _snapshot_path(source_category: str) -> str:
    return os.path.join(config.SNAPSHOTS_DIR, f"{source_category}.json")


def save_snapshot(events: List[Event], source_category: str) -> str:
    """Persist collected events as a cached_public snapshot."""
    os.makedirs(config.SNAPSHOTS_DIR, exist_ok=True)
    path = _snapshot_path(source_category)
    snapshot_events = []
    for ev in events:
        d = ev.to_dict()
        d["data_authenticity"] = CACHED_PUBLIC
        snapshot_events.append(d)
    payload = {
        "source_category": source_category,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "generated_from": "real public interface",
        "data_authenticity": CACHED_PUBLIC,
        "events": snapshot_events,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def list_snapshots() -> List[str]:
    if not os.path.isdir(config.SNAPSHOTS_DIR):
        return []
    return sorted(
        f for f in os.listdir(config.SNAPSHOTS_DIR) if f.endswith(".json")
    )


def load_snapshot(source_category: str) -> List[Event]:
    """Load a cached_public snapshot; every event is forced to cached_public."""
    path = _snapshot_path(source_category)
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    events = []
    for d in payload.get("events", []):
        d["data_authenticity"] = CACHED_PUBLIC
        d["source_category"] = source_category
        events.append(Event.from_dict(d))
    return events

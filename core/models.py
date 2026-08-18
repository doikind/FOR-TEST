"""Unified event model shared by collectors and the pipeline."""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

from core.authenticity import LIVE_PUBLIC


@dataclass
class Event:
    title: str
    source: str
    url: str
    published_at: str  # ISO-ish string; may be "" if source omits it
    collected_at: str
    source_category: str  # e.g. "rss", "gdelt", "hacker_news"
    data_authenticity: str = LIVE_PUBLIC

    # filled by the pipeline (standardization / scoring)
    normalized_title: str = ""
    category: str = "general"  # ai / fintech / crypto / investing / general
    heat_score: float = 0.0
    recency_score: float = 0.0
    category_score: float = 0.0
    feedback_score: float = 0.0
    priority_score: float = 0.0
    priority_reasons: Dict[str, Any] = field(default_factory=dict)
    dedup_key: str = ""
    merged_from: list = field(default_factory=list)
    follow_decision: str = ""  # follow/consider/caution/skip
    summary: str = ""
    angles: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

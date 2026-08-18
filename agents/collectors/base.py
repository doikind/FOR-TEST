"""Collector base types and shared helpers."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class SourceWarning:
    source: str
    reason: str


@dataclass
class CollectResult:
    events: List["object"] = field(default_factory=list)
    warnings: List[SourceWarning] = field(default_factory=list)


def make_ua() -> str:
    return "FinSignalContentAgent/1.0 (educational demo; contact: demo@example.com)"

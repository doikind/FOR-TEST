"""Data authenticity labels.

Every collected/derived data record carries exactly one of these three
labels, persisted and rendered in the UI so simulated vs real data is
never conflated.
"""

LIVE_PUBLIC = "live_public"
CACHED_PUBLIC = "cached_public"
SIMULATED_DEMO = "simulated_demo"

ALL = (LIVE_PUBLIC, CACHED_PUBLIC, SIMULATED_DEMO)


def is_valid(label: str) -> bool:
    return label in ALL

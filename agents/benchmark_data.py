"""Benchmark data loader for viral breakdown.

Primary case: Finimize (3 high + 3 normal). AlphaSense and Hebbia are
extension references only (never mixed into the primary grouping). If
Finimize real public data is insufficient, the loader can switch the primary
case to AlphaSense.
"""
import json
import os
from typing import Any, Dict, List

from core import config

PRIMARY_ACCOUNT = "Finimize"
EXTENSION_ACCOUNTS = ("AlphaSense", "Hebbia")


def load_finimize(path: str | None = None) -> Dict[str, Any]:
    path = path or os.path.join(config.SIMULATED_DIR, "finimize_posts.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_extension(account: str) -> Dict[str, Any]:
    """Load an extension-reference account dataset (simulated_demo)."""
    path = os.path.join(config.SIMULATED_DIR, f"{account.lower()}_posts.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_posts(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    posts = data.get("posts", [])
    for p in posts:
        p.setdefault("account", data.get("account", ""))
        p.setdefault("data_authenticity", data.get("data_authenticity", "simulated_demo"))
    return posts


def select_primary(finimize_posts: List[Dict[str, Any]]) -> tuple[str, List[Dict[str, Any]]]:
    """Return (account_name, posts) for the primary case.

    Switches to AlphaSense if Finimize data is insufficient (< 6 posts or
    missing key public metrics). AlphaSense is used only as fallback primary,
    never merged with Finimize.
    """
    enough = len(finimize_posts) >= 6 and all(
        p.get("metrics", {}).get("likes") is not None for p in finimize_posts
    )
    if enough:
        return PRIMARY_ACCOUNT, finimize_posts
    try:
        alpha = get_posts(load_extension("AlphaSense"))
        if len(alpha) >= 6:
            return "AlphaSense", alpha
    except FileNotFoundError:
        pass
    # fall back to whatever Finimize data exists (still labels evidence UNKNOWN)
    return PRIMARY_ACCOUNT, finimize_posts

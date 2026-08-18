"""X content discovery for Agent 2 — real public data.

Sources, in priority order:
  1. Nitter RSS (https://nitter.net/<screen_name>/rss) — real public timeline,
     typically 20 recent tweets with Post ID / full text / published time.
  2. x.com public profile page — server-rendered recent tweets (fallback).
No login, no API purchase, no private data. If all live sources fail, we fall
back to a compliant repo snapshot (cached_public / simulated_demo) and surface
the reason explicitly.
"""
import datetime as dt
import json
import re
import urllib.request
from typing import Any, Dict, List, Tuple

from agents.collectors.base import SourceWarning

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
PROFILE_URL = "https://x.com/{screen_name}"


def _fetch(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# --- Nitter RSS (primary) ------------------------------------------------------

def _rss_time_to_iso(published: str) -> str:
    if not published:
        return ""
    # nitter uses RFC822 with 'GMT'; feedparser gives us published_parsed too,
    # so try the parsed struct first, then fall back to strptime.
    try:
        parsed = dt.datetime.strptime(published, "%a, %d %b %Y %H:%M:%S %z")
        return parsed.astimezone(dt.timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        pass
    try:
        parsed = dt.datetime.strptime(published, "%a, %d %b %Y %H:%M:%S GMT")
        return parsed.replace(tzinfo=dt.timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        return ""


NITTER_INSTANCES = [
    # keep recently-working mirrors first; order = try order
    "https://nitter.tiekoetter.com/{screen_name}/rss",
    "https://nitter.projectsegfau.lt/{screen_name}/rss",
    "https://nitter.net/{screen_name}/rss",
    "https://nitter.poast.org/{screen_name}/rss",
    "https://nitter.privacydev.net/{screen_name}/rss",
    "https://nitter.1d4.us/{screen_name}/rss",
    "https://nitter.kavin.rocks/{screen_name}/rss",
]


def discover_from_nitter(screen_name: str) -> Tuple[List[Dict[str, Any]], List[SourceWarning]]:
    """Fetch and parse nitter RSS across public mirrors; return the richest result.

    Per-mirror failures are collapsed into one summary warning so the UI is
    not flooded with N identical 'HTTP 404 / 403 / SSL' lines.
    """
    import feedparser

    errors: List[str] = []
    best: List[Dict[str, Any]] = []
    for tpl in NITTER_INSTANCES:
        try:
            body = _fetch(tpl.format(screen_name=screen_name))
            parsed = feedparser.parse(body)
            tweets = []
            for e in parsed.entries:
                tid = e.get("id", "").strip()
                if not tid or not tid.isdigit():
                    continue
                tweets.append(
                    {
                        "post_id": tid,
                        "source_url": f"https://x.com/{screen_name}/status/{tid}",
                        "snippet": (e.get("title", "") or "")[:280],
                        "metrics": {},  # engagement not available via nitter RSS
                        "posted_at": _rss_time_to_iso(e.get("published", "")),
                        "data_authenticity": "live_public",
                    }
                )
            if len(tweets) > len(best):
                best = tweets
        except Exception as e:  # noqa: BLE001
            errors.append(f"{type(e).__name__}: {str(e)[:40]}")
    warnings: List[SourceWarning] = []
    if errors:
        # collapse: one summary line with the distinct error types
        kinds = sorted({e.split(":")[0] for e in errors})
        warnings.append(
            SourceWarning(
                "Nitter RSS",
                f"{len(errors)} mirrors unreachable ({', '.join(kinds)}); tried {len(NITTER_INSTANCES)}",
            )
        )
    if not best:
        warnings.append(SourceWarning("Nitter RSS", "no tweets parsed from any mirror"))
    return best, warnings


# --- x.com profile page (fallback) --------------------------------------------

def _clean_text(raw: str) -> str:
    t = raw.replace("\\n", " ").replace("\\u2019", "'").replace("\\u201c", '"').replace("\\u201d", '"')
    t = re.sub(r"https?://t\.co/\S+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _decode_tweet_id(b64: str) -> str:
    import base64

    try:
        raw = base64.b64decode(b64).decode("utf-8", errors="ignore")
        m = re.search(r"\d+", raw)
        return m.group(0) if m else ""
    except Exception:  # noqa: BLE001
        return ""


def discover_from_profile(screen_name: str) -> Tuple[List[Dict[str, Any]], List[SourceWarning]]:
    """Parse server-rendered tweets from x.com profile page."""
    warnings: List[SourceWarning] = []
    try:
        body = _fetch(PROFILE_URL.format(screen_name=screen_name)).decode("utf-8", errors="ignore")
        tweets = []
        seen = set()
        for m in re.finditer(r'VHdlZXQ6([A-Za-z0-9+/=]+):details.*?full_text:"(.*?)"', body, re.S):
            b64, full_text = m.group(1), m.group(2)
            tid = _decode_tweet_id(b64)
            if not tid or tid in seen:
                continue
            seen.add(tid)
            created = 0
            mm = re.search(r'created_at_ms:(\d+)', body[m.start(): m.start() + 4000])
            if mm:
                created = int(mm.group(1))
            tweets.append(
                {
                    "post_id": tid,
                    "source_url": f"https://x.com/{screen_name}/status/{tid}",
                    "snippet": _clean_text(full_text)[:280],
                    "metrics": {},
                    "posted_at": dt.datetime.fromtimestamp(created / 1000, tz=dt.timezone.utc).isoformat() if created else "",
                    "data_authenticity": "live_public",
                }
            )
        if not tweets:
            warnings.append(SourceWarning("X profile", "no tweets parsed"))
        return tweets, warnings
    except Exception as e:  # noqa: BLE001
        warnings.append(SourceWarning("X profile", f"{type(e).__name__}: {e}"))
        return [], warnings


# --- combined discovery --------------------------------------------------------

def discover_from_fxtwitter(screen_name: str, post_ids: List[str]) -> Dict[str, Dict[str, int]]:
    """Enrich tweets with real public engagement via FxTwitter (no login, no API key).

    FxTwitter is a public third-party proxy returning real tweet stats
    (likes / retweets / replies / views) for single tweets. Returns
    {post_id: {likes, retweets, replies, views}}.
    """
    import json

    out: Dict[str, Dict[str, int]] = {}
    for tid in post_ids:
        try:
            url = f"https://api.fxtwitter.com/{screen_name}/status/{tid}"
            req = urllib.request.Request(url, headers={"User-Agent": "finsignal/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                d = json.load(resp)
            t = d.get("tweet", {})
            out[tid] = {
                "likes": int(t.get("likes") or 0),
                "replies": int(t.get("replies") or 0),
                "reposts": int(t.get("retweets") or 0),
                "views": int(t.get("views") or 0),
            }
        except Exception:  # noqa: BLE001 — per-tweet enrichment is best-effort
            continue
    return out


def discover_from_x(screen_name: str) -> Tuple[List[Dict[str, Any]], List[SourceWarning]]:
    """Primary: nitter RSS (20 tweets) or x.com profile (5), enriched with real
    engagement from FxTwitter."""
    tweets, warnings = discover_from_nitter(screen_name)
    if not tweets:
        tweets2, warnings2 = discover_from_profile(screen_name)
        warnings.extend(warnings2)
        tweets = tweets2
    # enrich with real public engagement
    if tweets:
        ids = [t["post_id"] for t in tweets]
        engagement = discover_from_fxtwitter(screen_name, ids)
        for t in tweets:
            t["metrics"] = engagement.get(t["post_id"], {})
    return tweets, warnings


def load_snapshot(account: str) -> Dict[str, Any]:
    """Prefer the real X snapshot (20 real tweets) if present, else simulated data.

    Returns an empty posts payload (never raises) when neither exists, so an
    unknown/custom account degrades gracefully instead of crashing the UI.
    """
    import json
    import os

    from core import config

    x_path = os.path.join(config.SNAPSHOTS_DIR, f"x_{account.lower()}.json")
    if os.path.exists(x_path):
        with open(x_path, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        from agents import benchmark_data

        if account == "Finimize":
            return benchmark_data.load_finimize()
        return benchmark_data.load_extension(account)
    except FileNotFoundError:
        return {
            "account": account,
            "data_authenticity": "simulated_demo",
            "mode": "no_snapshot",
            "note": f"账号 @{account} 无可用快照（仓库中不存在对应数据文件）",
            "posts": [],
        }


def load_or_discover(account: str, prefer_live: bool = True) -> Dict[str, Any]:
    """Discovery entry: live X first, snapshot fallback with explicit note."""
    warnings: List[SourceWarning] = []
    if prefer_live:
        tweets, warnings = discover_from_x(account)
        if tweets:
            return {
                "account": account,
                "data_authenticity": "live_public",
                "mode": "live_x",
                "note": f"从 X 公开数据源实时解析 {len(tweets)} 条真实推文（nitter RSS / x.com）",
                "posts": tweets,
                "warnings": [{"source": w.source, "reason": w.reason} for w in warnings],
            }
    data = load_snapshot(account)
    posts = data.get("posts", [])
    for p in posts:
        p.setdefault("account", account)
    # distinguish "snapshot exists" vs "no data at all" in the note
    if posts:
        note = data.get("note", "真实公开数据快照")
        mode = "snapshot_fallback"
        if not warnings:
            warnings.append(SourceWarning("X discovery", "live X unreachable, using repo snapshot"))
    else:
        note = data.get("note", f"账号 @{account} 无可用的实时数据或快照")
        mode = "no_data"
        warnings.append(SourceWarning("X discovery", note))
    return {
        "account": account,
        "data_authenticity": data.get("data_authenticity", "simulated_demo"),
        "mode": mode,
        "note": note,
        "posts": posts,
        "warnings": [{"source": w.source, "reason": w.reason} for w in warnings],
    }

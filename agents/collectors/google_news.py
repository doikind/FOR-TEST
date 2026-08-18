"""Google News RSS collector — primary news discovery source.

Keeps only news from authoritative/official outlets (or at least clearly
mainstream professional media). Google News encodes the outlet in the
headline suffix ('Headline - Outlet'), which we parse and filter:

  - tier1: globally authoritative / domain-core outlets → kept, marked "official"
  - tier2: other recognizable professional media → kept, marked "media"
  - block: personal blogs, SEO/aggregator junk, unknown domains → dropped
"""
import datetime as dt
from typing import List

import feedparser

from agents.collectors.base import CollectResult, SourceWarning, make_ua
from core.authenticity import LIVE_PUBLIC
from core.models import Event

# Global queries always run; region-specific ones follow the account profile.
BASE_URL = "https://news.google.com/rss/search"
GLOBAL_QUERIES = [
    "AI fintech",
    "artificial intelligence investing",
]
# {keyword} 会被替换为画像的地区名（如 Philippines / Singapore）
REGION_QUERY_TPL = [
    "fintech {region}",
    "digital finance {region}",
    "AI finance {region}",
]
PER_QUERY_LIMIT = 8  # fetch a few extra, then filter to ~20 official items

# Tier-1: globally authoritative or directly domain-core outlets.
TIER1_OUTLETS = (
    "reuters", "bloomberg", "financial times", "ft.com", "wsj", "the wall street journal",
    "cnbc", "business insider", "forbes", "economist", "bbc", "cnn", "nbc news",
    "fintech singapore", "fintech global", "the business times", "business times",
    "techcrunch", "the edge", "investing.com", "marketwatch", "blackrock",
    "singapore business review", "finews.asia", "asia financial", "crypto news",
    "the straits times", "channel news asia", "cna", "nikkei", "asia nikkei",
    "al jazeera", "ap", "associated press", "guardian", "reuters asia",
    # Philippines
    "philippine star", "philstar", "inquirer", "manila times", "businessworld",
    "rappler", "business mirror", "gma news", "abs-cbn", "pna", "philippine news agency",
    "manila bulletin",
    # Indonesia / Malaysia / Thailand / Vietnam
    "jakarta post", "kompas", "detik", "tempo", "the star malaysia", "malay mail",
    "new straits times", "berita harian", "bangkok post", "nation thailand",
    "vietnam news", "vnexpress", "tuoi tre", "thanh nien", "vietnam investment",
)

# Tier-2: recognizable professional media (kept, but flagged as 'media').
TIER2_OUTLETS = (
    "siliconrepublic.com", "wealth professional", "funds society", "moit.gov",
    "et cio", "the fintech times", "finews", "ifamagazine", "pymnts",
    "american banker", "the banker", "finextra", "altfi", "crowdfund insider",
    "singapore business", "focus", "dealstreetasia", "e27", "vulcan post",
)

# Personal-blog / SEO / aggregator junk patterns → drop.
BLOCK_PATTERNS = (
    "medium.com", "substack", "wordpress", "blogspot", "quora", "reddit",
    "linkedin.com/pulse", "seeking alpha", "motley fool", "benzinga",
    "investorplace", "simplywall.st", "stocktwits", "thestreet",
)

# Unprofessional-looking domain TLDs → drop unless tier-listed.
_BLOCK_TLDS = (".xyz", ".top", ".online", ".site", ".icu", ".club", ".biz", ".info")


def _parse_outlet(title: str) -> str:
    """Extract the outlet name from 'Headline - Outlet'."""
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return ""


def _outlet_quality(outlet: str) -> str:
    """Return 'official' | 'media' | 'block' | '' (unknown)."""
    o = outlet.lower().strip()
    if not o:
        return ""
    if any(t in o for t in TIER1_OUTLETS):
        return "official"
    if any(t in o for t in TIER2_OUTLETS):
        return "media"
    if any(p in o for p in BLOCK_PATTERNS):
        return "block"
    if any(o.endswith(t) for t in _BLOCK_TLDS):
        return "block"
    # single unknown word outlets (e.g. 'Qazinform') → block; keep multi-word
    # outlets that look like real news brands
    if " " not in o and len(o) < 14 and "." not in o:
        return "block"
    return "media" if len(o) >= 3 else "block"


def _iso_from_entry(entry) -> str:
    for key in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, key, None)
        if parsed:
            try:
                return dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc).isoformat()
            except Exception:
                pass
    return ""


def _profile_regions() -> list:
    """Regions from the current account profile (for region queries)."""
    try:
        from core.account import load_profile

        p = load_profile()
        return p.get("regions") or ["Singapore"]
    except Exception:  # noqa: BLE001
        return ["Singapore"]


def _build_queries(query: str | None = None) -> list:
    """Global queries + region queries driven by the account profile.

    Returns [(query, per_query_limit)] — region queries fetch more items so
    the profile's target region dominates the pool.
    """
    if query:
        return [(query, PER_QUERY_LIMIT)]
    regions = _profile_regions()
    qs = [(q, 4) for q in GLOBAL_QUERIES]           # global: fewer
    for r in regions:
        for tpl in REGION_QUERY_TPL:
            qs.append((tpl.format(region=r), 10))    # region: more
    return qs


def _locale_for(region: str) -> tuple[str, str]:
    """(hl, gl) for a region — best-effort, default SG."""
    table = {
        "Singapore": ("en-SG", "SG"),
        "Philippines": ("en-PH", "PH"),
        "Indonesia": ("en-ID", "ID"),
        "Malaysia": ("en-MY", "MY"),
        "Thailand": ("en-TH", "TH"),
        "Vietnam": ("en-VN", "VN"),
        "US": ("en-US", "US"),
        "China": ("en-CN", "CN"),
        "Japan": ("en-JP", "JP"),
        "Europe": ("en-GB", "GB"),
        "Global": ("en-US", "US"),
        "Southeast Asia (general)": ("en-SG", "SG"),
    }
    return table.get(region, ("en-SG", "SG"))


def collect(query: str | None = None) -> CollectResult:
    result = CollectResult()
    queries = _build_queries(query)
    regions = _profile_regions()
    hl, gl = _locale_for(regions[0] if regions else "Singapore")
    collected_at = dt.datetime.now(dt.timezone.utc).isoformat()
    seen = set()
    dropped = 0
    for q, qlimit in queries:
        try:
            url = f"{BASE_URL}?q={q.replace(' ', '+')}&hl={hl}&gl={gl}&ceid={gl}:en"
            parsed = feedparser.parse(url, request_headers={"User-Agent": make_ua()})
            for entry in parsed.entries[:qlimit]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                if not title or not link or link in seen:
                    continue
                outlet = _parse_outlet(title)
                quality = _outlet_quality(outlet)
                if quality == "block":
                    dropped += 1
                    continue
                seen.add(link)
                tier_tag = "[官方]" if quality == "official" else "[媒体]"
                result.events.append(
                    Event(
                        title=title,
                        source=f"Google News · {outlet} {tier_tag}" if outlet else "Google News",
                        url=link,
                        published_at=_iso_from_entry(entry),
                        collected_at=collected_at,
                        source_category="google_news",
                        data_authenticity=LIVE_PUBLIC,
                    )
                )
        except Exception as e:  # noqa: BLE001
            result.warnings.append(SourceWarning("Google News RSS", f"{type(e).__name__}: {e}"))
    if dropped:
        result.warnings.append(SourceWarning("Google News RSS", f"过滤 {dropped} 条非官方/低质来源"))
    return result


def collect_more(query: str | None = None) -> CollectResult:
    """Deeper collection for '需要更多热点' — larger per-query limit."""
    import agents.collectors.google_news as _self

    _old = _self.PER_QUERY_LIMIT
    _self.PER_QUERY_LIMIT = 15
    try:
        return _self.collect(query)
    finally:
        _self.PER_QUERY_LIMIT = _old

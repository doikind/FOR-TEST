"""CoinGecko collector — optional supplement for Crypto/digital-finance events.

Free public endpoint (no key). This is a P1 optional source: failures are
reported as warnings and never block the pipeline, and no data is fabricated.
"""
import datetime as dt
import json
import urllib.request
from typing import List

from agents.collectors.base import CollectResult, SourceWarning, make_ua
from core.authenticity import LIVE_PUBLIC
from core.models import Event

# Free endpoint: top coins by market cap. Used only to surface notable
# crypto/digital-finance movements as candidate events.
MARKETS_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
    "&sparkline=false&price_change_percentage=24h"
)


def collect() -> CollectResult:
    result = CollectResult()
    collected_at = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        req = urllib.request.Request(MARKETS_URL, headers={"User-Agent": make_ua()})
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.load(resp)
    except Exception as e:  # noqa: BLE001
        result.warnings.append(SourceWarning("CoinGecko", f"{type(e).__name__}: {e}"))
        return result

    for coin in data:
        name = coin.get("name", "")
        symbol = (coin.get("symbol", "") or "").upper()
        price_change = coin.get("price_change_percentage_24h")
        if price_change is None:
            continue
        title = f"{name} ({symbol}) 24h price change {price_change:.2f}%"
        result.events.append(
            Event(
                title=title,
                source="CoinGecko",
                url=f"https://www.coingecko.com/en/coins/{coin.get('id','')}",
                published_at=collected_at,
                collected_at=collected_at,
                source_category="coingecko",
                data_authenticity=LIVE_PUBLIC,
                heat_score=abs(price_change),
            )
        )
    return result

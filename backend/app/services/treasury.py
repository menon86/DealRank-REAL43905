"""10-Year Treasury constant-maturity yield (FRED series DGS10).

Read from FRED's public CSV endpoint (no API key), cached in-process for
six hours. If FRED is unreachable (it has maintenance outages) the same
yield is read from the US Treasury's own daily par yield curve feed. If
both fail the configured fallback yield is returned and labelled
source="fallback" so callers can surface that it is not a live quote. Callers
can also bypass all of this with an explicit override.
"""

from __future__ import annotations

import csv
import io
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import httpx

from app.config import get_settings

CACHE_TTL_SECONDS = 6 * 60 * 60

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TreasuryQuote:
    yield_: Decimal  # decimal fraction, 0.0431 = 4.31%
    as_of: date | None
    source: str  # "fred" | "treasury" | "fallback" | "override"


# A failed lookup is remembered briefly so an outage costs one 5-second
# timeout per minute, not one per request.
FAILURE_BACKOFF_SECONDS = 60

_cache: tuple[float, TreasuryQuote] | None = None
_last_failure: float | None = None


def parse_fred_csv(text: str) -> TreasuryQuote:
    """Latest non-missing observation. FRED writes missing days as '.'."""
    reader = csv.reader(io.StringIO(text))
    next(reader, None)  # header: observation_date,DGS10
    latest: tuple[date, Decimal] | None = None
    for row in reader:
        if len(row) < 2 or row[1].strip() in ("", "."):
            continue
        latest = (date.fromisoformat(row[0]), Decimal(row[1]) / 100)
    if latest is None:
        raise ValueError("FRED response contained no observations")
    return TreasuryQuote(yield_=latest[1], as_of=latest[0], source="fred")


def parse_treasury_xml(text: str) -> TreasuryQuote:
    """Latest BC_10YEAR par yield from the Treasury daily yield curve feed."""
    latest: tuple[date, Decimal] | None = None
    for props in ET.fromstring(text).iterfind(".//{*}properties"):
        day = props.findtext("{*}NEW_DATE")
        rate = props.findtext("{*}BC_10YEAR")
        if not day or not rate or not rate.strip():
            continue
        row = (date.fromisoformat(day[:10]), Decimal(rate) / 100)
        if latest is None or row[0] > latest[0]:
            latest = row
    if latest is None:
        raise ValueError("Treasury response contained no 10-year observations")
    return TreasuryQuote(yield_=latest[1], as_of=latest[0], source="treasury")


def _fetch(url: str, parse) -> TreasuryQuote:
    resp = httpx.get(url, timeout=5.0, follow_redirects=True, headers={"User-Agent": "DealRank"})
    resp.raise_for_status()
    return parse(resp.text)


def get_treasury_10y(*, use_cache: bool = True) -> TreasuryQuote:
    global _cache, _last_failure
    now = time.monotonic()
    if use_cache and _cache is not None and now - _cache[0] < CACHE_TTL_SECONDS:
        return _cache[1]
    settings = get_settings()
    fallback = TreasuryQuote(yield_=settings.TREASURY_10Y_FALLBACK, as_of=None, source="fallback")
    if use_cache and _last_failure is not None and now - _last_failure < FAILURE_BACKOFF_SECONDS:
        return fallback
    today = date.today()
    # Previous month too: the current month's feed is empty on the first days of a month.
    prior = (today.replace(day=1) - timedelta(days=1)).strftime("%Y%m")
    sources = [(settings.FRED_SERIES_URL, parse_fred_csv)]
    for month in (today.strftime("%Y%m"), prior):
        sources.append((settings.TREASURY_YIELD_CURVE_URL.format(month=month), parse_treasury_xml))
    for url, parse in sources:
        try:
            quote = _fetch(url, parse)
        except (httpx.HTTPError, ValueError, ArithmeticError, ET.ParseError) as exc:
            logger.warning("Treasury yield lookup failed for %s: %r", url, exc)
            continue
        _last_failure = None
        _cache = (now, quote)
        return quote
    # Every source failed: remember it briefly so an outage doesn't cost a
    # timeout per source on every request.
    _last_failure = now
    return fallback


def override_quote(yield_: Decimal) -> TreasuryQuote:
    return TreasuryQuote(yield_=yield_, as_of=None, source="override")


def clear_cache() -> None:
    global _cache, _last_failure
    _cache = None
    _last_failure = None

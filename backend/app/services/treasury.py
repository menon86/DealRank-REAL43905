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
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import httpx

from app.config import get_settings

CACHE_TTL_SECONDS = 6 * 60 * 60


@dataclass(frozen=True)
class TreasuryQuote:
    yield_: Decimal  # decimal fraction, 0.0431 = 4.31%
    as_of: date | None
    source: str  # "fred" | "treasury" | "fallback" | "override"


_cache: tuple[float, TreasuryQuote] | None = None


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
    global _cache
    now = time.monotonic()
    if use_cache and _cache is not None and now - _cache[0] < CACHE_TTL_SECONDS:
        return _cache[1]
    settings = get_settings()
    sources = (
        (settings.FRED_SERIES_URL, parse_fred_csv),
        (settings.TREASURY_YIELD_CURVE_URL.format(year=date.today().year), parse_treasury_xml),
    )
    for url, parse in sources:
        try:
            quote = _fetch(url, parse)
        except (httpx.HTTPError, ValueError, ArithmeticError, ET.ParseError):
            continue
        _cache = (now, quote)
        return quote
    return TreasuryQuote(yield_=settings.TREASURY_10Y_FALLBACK, as_of=None, source="fallback")


def override_quote(yield_: Decimal) -> TreasuryQuote:
    return TreasuryQuote(yield_=yield_, as_of=None, source="override")


def clear_cache() -> None:
    global _cache
    _cache = None

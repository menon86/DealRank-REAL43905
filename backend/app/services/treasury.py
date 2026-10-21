"""10-Year Treasury constant-maturity yield (FRED series DGS10).

Read from FRED's public CSV endpoint (no API key), cached in-process for
six hours. If the lookup fails the configured fallback yield is returned
and labelled source="fallback" so callers can surface that it is not a
live quote. Callers can also bypass all of this with an explicit override.
"""

from __future__ import annotations

import csv
import io
import time
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
    source: str  # "fred" | "fallback" | "override"


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


def get_treasury_10y(*, use_cache: bool = True) -> TreasuryQuote:
    global _cache, _last_failure
    now = time.monotonic()
    if use_cache and _cache is not None and now - _cache[0] < CACHE_TTL_SECONDS:
        return _cache[1]
    settings = get_settings()
    fallback = TreasuryQuote(yield_=settings.TREASURY_10Y_FALLBACK, as_of=None, source="fallback")
    if use_cache and _last_failure is not None and now - _last_failure < FAILURE_BACKOFF_SECONDS:
        return fallback
    try:
        resp = httpx.get(settings.FRED_SERIES_URL, timeout=5.0, follow_redirects=True)
        resp.raise_for_status()
        quote = parse_fred_csv(resp.text)
    except (httpx.HTTPError, ValueError, ArithmeticError):
        _last_failure = now
        return fallback
    _last_failure = None
    _cache = (now, quote)
    return quote


def override_quote(yield_: Decimal) -> TreasuryQuote:
    return TreasuryQuote(yield_=yield_, as_of=None, source="override")


def clear_cache() -> None:
    global _cache, _last_failure
    _cache = None
    _last_failure = None

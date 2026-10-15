from datetime import date
from decimal import Decimal as D

import httpx
import pytest

from app.services import treasury

FRED_CSV = """observation_date,DGS10
2026-10-09,4.12
2026-10-12,.
2026-10-13,4.31
2026-10-14,.
"""


def test_parse_takes_latest_non_missing_observation_as_a_fraction():
    quote = treasury.parse_fred_csv(FRED_CSV)
    assert quote.yield_ == D("0.0431")
    assert quote.as_of == date(2026, 10, 13)
    assert quote.source == "fred"


def test_parse_rejects_empty_series():
    with pytest.raises(ValueError):
        treasury.parse_fred_csv("observation_date,DGS10\n2026-10-12,.\n")


@pytest.fixture(autouse=True)
def _fresh_cache():
    treasury.clear_cache()
    yield
    treasury.clear_cache()


def _mock_get(monkeypatch, handler):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return handler(url)

    monkeypatch.setattr(treasury.httpx, "get", fake_get)
    return calls


def test_live_quote_is_cached(monkeypatch):
    calls = _mock_get(
        monkeypatch,
        lambda url: httpx.Response(200, text=FRED_CSV, request=httpx.Request("GET", url)),
    )
    assert treasury.get_treasury_10y().yield_ == D("0.0431")
    assert treasury.get_treasury_10y().yield_ == D("0.0431")
    assert len(calls) == 1


def test_failure_falls_back_to_configured_yield_and_says_so(monkeypatch):
    def boom(url):
        raise httpx.ConnectError("blocked")

    _mock_get(monkeypatch, boom)
    quote = treasury.get_treasury_10y()
    assert quote.source == "fallback" and quote.as_of is None
    assert quote.yield_ == D("0.046")


def test_http_error_status_also_falls_back(monkeypatch):
    _mock_get(monkeypatch, lambda url: httpx.Response(503, request=httpx.Request("GET", url)))
    assert treasury.get_treasury_10y().source == "fallback"
    # A fallback is not cached: the next call tries the network again.
    _mock_get(
        monkeypatch,
        lambda url: httpx.Response(200, text=FRED_CSV, request=httpx.Request("GET", url)),
    )
    assert treasury.get_treasury_10y().source == "fred"


def test_override():
    q = treasury.override_quote(D("0.05"))
    assert (q.yield_, q.source) == (D("0.05"), "override")

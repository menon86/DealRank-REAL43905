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


TREASURY_XML = """<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
 xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
<entry><content><m:properties>
<d:NEW_DATE m:type="Edm.DateTime">2026-10-19T00:00:00</d:NEW_DATE>
<d:BC_10YEAR m:type="Edm.Double">5.10</d:BC_10YEAR>
</m:properties></content></entry>
<entry><content><m:properties>
<d:NEW_DATE m:type="Edm.DateTime">2026-10-20T00:00:00</d:NEW_DATE>
<d:BC_10YEAR m:type="Edm.Double">5.12</d:BC_10YEAR>
</m:properties></content></entry>
</feed>"""


def test_parse_treasury_xml_takes_latest_date():
    quote = treasury.parse_treasury_xml(TREASURY_XML)
    assert (quote.yield_, quote.as_of, quote.source) == (
        D("0.0512"),
        date(2026, 10, 20),
        "treasury",
    )


def test_fred_maintenance_page_falls_through_to_treasury_gov(monkeypatch):
    def handler(url):
        text = "<html>Site Maintenance</html>" if "fred" in url else TREASURY_XML
        return httpx.Response(200, text=text, request=httpx.Request("GET", url))

    _mock_get(monkeypatch, handler)
    quote = treasury.get_treasury_10y()
    assert (quote.source, quote.yield_) == ("treasury", D("0.0512"))


def test_empty_current_month_uses_previous_month(monkeypatch):
    empty = "<feed xmlns='http://www.w3.org/2005/Atom'/>"
    calls = _mock_get(
        monkeypatch,
        lambda url: httpx.Response(
            200,
            text=TREASURY_XML if len(calls) == 3 else empty if "fred" not in url else "<html/>",
            request=httpx.Request("GET", url),
        ),
    )
    quote = treasury.get_treasury_10y()
    assert quote.source == "treasury" and len(calls) == 3


def test_http_error_status_also_falls_back(monkeypatch):
    _mock_get(monkeypatch, lambda url: httpx.Response(503, request=httpx.Request("GET", url)))
    assert treasury.get_treasury_10y().source == "fallback"
    # A fallback is not cached as a quote, but the failure is remembered for a
    # minute so an outage doesn't cost a timeout on every request.
    _mock_get(
        monkeypatch,
        lambda url: httpx.Response(200, text=FRED_CSV, request=httpx.Request("GET", url)),
    )
    assert treasury.get_treasury_10y().source == "fallback"
    # After the backoff (or a forced refresh) the network is tried again.
    assert treasury.get_treasury_10y(use_cache=False).source == "fred"


def test_failed_lookup_is_not_retried_within_the_backoff(monkeypatch):
    calls = []

    def boom(url):
        calls.append(url)
        raise httpx.ConnectError("down")

    _mock_get(monkeypatch, boom)
    assert treasury.get_treasury_10y().source == "fallback"
    tried = len(calls)  # one attempt per source on the first lookup
    for _ in range(2):
        assert treasury.get_treasury_10y().source == "fallback"
    assert len(calls) == tried


def test_override():
    q = treasury.override_quote(D("0.05"))
    assert (q.yield_, q.source) == (D("0.05"), "override")

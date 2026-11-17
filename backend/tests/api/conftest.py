"""Test client fixture for API tests. See docs/build-plan.md Phase 4 —
tests run against the app on the Phase 0.3 test database (db_session from
the parent conftest), not the dev database.
"""

from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.auth import current_owner, require_user
from app.db import get_db
from app.models.cap_rate_spread import CapRateSpread

# The owner_id the `client` fixture's requests run as.
TEST_OWNER = "test-owner"


@pytest.fixture()
def client(db_session) -> Generator[TestClient, None, None]:
    # Imported here, not at module scope: app.main reads settings (and
    # therefore DATABASE_URL) at import time, and we want that to happen
    # only once a test actually needs it, after conftest has confirmed
    # DATABASE_URL is set.
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    # Most tests aren't about sign-in, so they run as an already signed-in user.
    # test_auth.py uses anon_client to exercise the real check.
    app.dependency_overrides[require_user] = lambda: None
    app.dependency_overrides[current_owner] = lambda: TEST_OWNER

    # FastAPI's TestClient (httpx under the hood) bridges the sync test
    # to the ASGI app itself — plain httpx.Client + ASGITransport only
    # supports the async interface, which would need pytest-asyncio.
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(db_session) -> Generator[TestClient, None, None]:
    """Like client, but with the real sign-in check (no user overridden in)."""
    from app.main import app
    from app.services.rate_limit import auth_limiter

    auth_limiter.reset()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    auth_limiter.reset()


@pytest.fixture()
def spreads(db_session):
    for cls, bps, growth in [
        ("student_housing", 130, "0.0200"),
        ("suburban_garden", 61, "0.0140"),
        ("urban_midrise", 60, "0.0140"),
    ]:
        db_session.add(
            CapRateSpread(
                sub_asset_class=cls,
                survey_source="test survey",
                survey_quarter="2026H1",
                spread_bps=bps,
                assumed_stabilized_noi_growth=Decimal(growth),
                effective_date=date(2026, 8, 12),
            )
        )
    db_session.flush()


# ---- shared by the chat tests (test_chat_*.py) ----

CHAT_TREASURY = "0.046"


@pytest.fixture()
def chat_treasury(monkeypatch):
    """Pins the Treasury lookup so no chat test touches the network. Returns a dict whose
    "source" ("fred" = live, "fallback" = the labelled default) the test can change."""
    from app.services.treasury import TreasuryQuote

    state = {"source": "fred"}

    def fake():
        as_of = date(2026, 10, 1) if state["source"] != "fallback" else None
        return TreasuryQuote(Decimal(CHAT_TREASURY), as_of, state["source"])

    monkeypatch.setattr("app.api.risk_rank.get_treasury_10y", fake)
    return state


@pytest.fixture()
def chat_deals(db_session, spreads, chat_treasury):
    """The three seed deals (ORM rows) with cap-rate spreads loaded.
    Hurdles at a 4.6% Treasury: student 7.90%, garden 6.61%, mid-rise 6.60%."""
    from app.models.deal import Deal
    from tests.api.payloads import (
        STUDENT_HOUSING_PAYLOAD,
        SUBURBAN_GARDEN_PAYLOAD,
        URBAN_MIDRISE_PAYLOAD,
    )

    deals = {}
    for payload in (STUDENT_HOUSING_PAYLOAD, SUBURBAN_GARDEN_PAYLOAD, URBAN_MIDRISE_PAYLOAD):
        deal = Deal(**payload, owner_id=TEST_OWNER)
        db_session.add(deal)
        deals[payload["name"]] = deal
    db_session.flush()
    for deal in deals.values():
        db_session.refresh(deal)  # coerce payload strings to enums/Decimals
    return deals

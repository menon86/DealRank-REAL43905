"""Test client fixture for API tests. See docs/build-plan.md Phase 4 —
tests run against the app on the Phase 0.3 test database (db_session from
the parent conftest), not the dev database.
"""

from collections.abc import Generator
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.cap_rate_spread import CapRateSpread


@pytest.fixture()
def client(db_session) -> Generator[TestClient, None, None]:
    # Imported here, not at module scope: app.main reads settings (and
    # therefore DATABASE_URL) at import time, and we want that to happen
    # only once a test actually needs it, after conftest has confirmed
    # DATABASE_URL is set.
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db_session

    # FastAPI's TestClient (httpx under the hood) bridges the sync test
    # to the ASGI app itself — plain httpx.Client + ASGITransport only
    # supports the async interface, which would need pytest-asyncio.
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


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

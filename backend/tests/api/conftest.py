"""Test client fixture for API tests. See docs/build-plan.md Phase 4 —
tests run against the app on the Phase 0.3 test database (db_session from
the parent conftest), not the dev database.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.db import get_db


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

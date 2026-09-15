"""Test database fixtures. See docs/build-plan.md 0.3.

DATABASE_URL points at the dev database (see backend/.env.example); tests
run against a separate `dealrank_test` database so `pytest` never touches
dev data, created on demand and migrated to head once per test session.
Each individual test runs inside a transaction that's rolled back at
teardown, so tests never see each other's writes regardless of order.
"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _test_database_url() -> str:
    """Builds the dealrank_test connection string. Uses render_as_string
    with hide_password=False — plain str(url) / url.set(...) masks the
    password as "***" (SQLAlchemy's default, meant for logging), which
    would make every downstream connection built from this string
    authenticate with the literal text "***" instead of the real
    password.
    """
    base_url = os.environ["DATABASE_URL"]
    url = sa.engine.make_url(base_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


def _ensure_database_exists(test_url: str) -> None:
    url = sa.engine.make_url(test_url)
    admin_url = url.set(database="postgres")
    admin_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                sa.text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            ).scalar()
            if not exists:
                conn.execute(sa.text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin_engine.dispose()


def _run_migrations(test_url: str) -> None:
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url
    try:
        command.upgrade(alembic_cfg, "head")
    finally:
        if previous is not None:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture(scope="session")
def test_db_engine() -> Generator[sa.engine.Engine, None, None]:
    test_url = _test_database_url()
    _ensure_database_exists(test_url)
    _run_migrations(test_url)

    engine = sa.create_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_db_engine: sa.engine.Engine) -> Generator[Session, None, None]:
    """One connection per test, wrapped in a transaction that's always
    rolled back — the DB is reset to migrated-but-empty for every test,
    so two tests writing the same deal name both pass regardless of
    execution order.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

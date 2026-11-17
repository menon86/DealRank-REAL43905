"""The one list of sample deals, and seed.py loading it."""

import seed
from app.demo import DEMO_TEMPLATE_OWNER
from app.models import Deal
from app.sample_deals import SAMPLE_DEALS

DELETED_ON_PURPOSE = {
    "Cedar Point Villas",
    "Heritage Park Townhomes",
    "Oak Hall Residences",
    "Skyline Plaza",
    "Stadium Row Lofts",
    "The Quad at Riverside",
}


def test_sample_deals_are_the_twelve_we_kept():
    names = [d["name"] for d in SAMPLE_DEALS]
    assert len(names) == len(set(names)) == 12
    assert not DELETED_ON_PURPOSE & set(names)


def test_every_sample_deal_is_a_valid_deal(db_session):
    db_session.add_all(Deal(**d, owner_id="check@example.com") for d in SAMPLE_DEALS)
    db_session.flush()
    assert db_session.query(Deal).filter(Deal.owner_id == "check@example.com").count() == 12


def test_seed_moves_old_deals_into_the_template_without_duplicates(db_session, monkeypatch):
    monkeypatch.setattr(seed, "create_engine", lambda url: db_session.get_bind())
    monkeypatch.setattr(seed, "Session", lambda engine: _Keep(db_session))
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")

    # Two sample deals already in the database from before sign-in (no owner).
    db_session.add_all(Deal(**d) for d in SAMPLE_DEALS[:2])
    db_session.flush()

    seed.main()
    seed.main()  # idempotent
    rows = db_session.query(Deal.owner_id, Deal.name).all()
    assert {o for o, _ in rows} == {DEMO_TEMPLATE_OWNER}
    assert sorted(n for _, n in rows) == sorted(d["name"] for d in SAMPLE_DEALS)


def test_seed_leaves_users_own_deals_alone(db_session, monkeypatch):
    monkeypatch.setattr(seed, "create_engine", lambda url: db_session.get_bind())
    monkeypatch.setattr(seed, "Session", lambda engine: _Keep(db_session))
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")

    db_session.add(Deal(**SAMPLE_DEALS[0], owner_id="me@example.com"))
    db_session.flush()
    seed.main()
    mine = db_session.query(Deal).filter(Deal.owner_id == "me@example.com").count()
    assert mine == 1


class _Keep:
    """Lets seed.main() use the test session without closing it."""

    def __init__(self, session):
        self._s = session

    def __enter__(self):
        return self._s

    def __exit__(self, *exc):
        return False

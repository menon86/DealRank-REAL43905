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


def test_seed_is_idempotent_and_never_re_adds_deleted_deals(db_session, monkeypatch):
    monkeypatch.setattr(seed, "create_engine", lambda url: db_session.get_bind())
    monkeypatch.setattr(seed, "Session", lambda engine: _Keep(db_session))
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")

    def counts():
        rows = db_session.query(Deal.owner_id).all()
        return {o: sum(1 for (x,) in rows if x == o) for o in {o for (o,) in rows}}

    seed.main()
    assert counts() == {DEMO_TEMPLATE_OWNER: 12, seed.SEED_OWNER_EMAIL: 12}

    # The owner deletes a deal; another deploy must not bring it back.
    gone = db_session.query(Deal).filter(Deal.owner_id == seed.SEED_OWNER_EMAIL).first()
    db_session.delete(gone)
    db_session.flush()
    seed.main()
    assert counts() == {DEMO_TEMPLATE_OWNER: 12, seed.SEED_OWNER_EMAIL: 11}


class _Keep:
    """Lets seed.main() use the test session without closing it."""

    def __init__(self, session):
        self._s = session

    def __enter__(self):
        return self._s

    def __exit__(self, *exc):
        return False

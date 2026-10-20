from sqlalchemy import func, select

from app.models.market_rent import MarketRent
from seed_market_rents import SEED_CSV, seed


def test_bundled_csv_seeds_once_and_covers_known_metros(db_session):
    first = seed(db_session)
    assert first is not None and first[0] > 10_000 and first[1] == 0

    geographies = set(db_session.scalars(select(MarketRent.geography).distinct()))
    assert {"Indianapolis, IN", "Lafayette, IN"} <= geographies
    assert SEED_CSV.stat().st_size < 1_000_000

    count = db_session.scalar(select(func.count()).select_from(MarketRent))
    assert seed(db_session) is None
    assert db_session.scalar(select(func.count()).select_from(MarketRent)) == count

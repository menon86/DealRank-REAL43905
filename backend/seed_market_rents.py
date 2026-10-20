"""Seed market_rents with the bundled Zillow ZORI metro CSV (data/README.md).

Does nothing once Zillow rows exist, so rents loaded later through the app
or ingest_market_rents.py are never overwritten.

Usage (with DATABASE_URL set):
    python seed_market_rents.py
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.config import normalize_database_url
from app.models.market_rent import MarketRent
from app.services.market_rents import ALL_CLASSES, load_rows, parse_wide_rent_csv

SOURCE = "zillow_zori"
SEED_CSV = Path(__file__).parent / "data" / "zillow_zori_metro_all_homes_plus_multifamily.csv"


def seed(session: Session, csv_path: Path = SEED_CSV) -> tuple[int, int] | None:
    """Loads the CSV unless Zillow rows already exist. Returns (inserted,
    updated), or None when skipped.
    """
    existing = session.scalar(
        select(func.count()).select_from(MarketRent).where(MarketRent.source == SOURCE)
    )
    if existing:
        return None
    rows = parse_wide_rent_csv(csv_path.read_text(encoding="utf-8-sig"))
    result = load_rows(session, SOURCE, rows, ALL_CLASSES)
    session.commit()
    return result


def main() -> None:
    engine = create_engine(normalize_database_url(os.environ["DATABASE_URL"]))
    with Session(engine) as session:
        result = seed(session)
    if result is None:
        print("Market rents already loaded. Skipping.")
    else:
        print(f"Market rents seeded: {result[0]} rows inserted.")


if __name__ == "__main__":
    main()

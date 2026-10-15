"""Load a Zillow ZORI or Apartment List rent CSV into market_rents.

Download the CSV by hand (these are published as files, not APIs):
  Zillow:         https://www.zillow.com/research/data/  -> "ZORI" (Observed Rent Index)
  Apartment List: https://www.apartmentlist.com/research/category/data-rent-estimates

Usage (DATABASE_URL set):
    python ingest_market_rents.py zillow_zori path/to/Metro_zori.csv
    python ingest_market_rents.py apartment_list path/to/rents.csv --months 36

Idempotent: re-running on a refreshed file updates changed values in place.
"""

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import normalize_database_url
from app.services.market_rents import ALL_CLASSES, SOURCES, load_rows, parse_wide_rent_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", choices=sorted(SOURCES))
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--months", type=int, default=24, help="most recent months to keep")
    parser.add_argument("--sub-asset-class", default=ALL_CLASSES)
    args = parser.parse_args()

    rows = parse_wide_rent_csv(args.csv_path.read_text(encoding="utf-8-sig"), args.months)
    engine = create_engine(normalize_database_url(os.environ["DATABASE_URL"]))
    with Session(engine) as session:
        inserted, updated = load_rows(session, args.source, rows, args.sub_asset_class)
        session.commit()
    print(f"{SOURCES[args.source]}: {inserted} rows inserted, {updated} updated.")


if __name__ == "__main__":
    main()

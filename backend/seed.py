"""Load the sample deals (app/sample_deals.py).

Usage (with DATABASE_URL set, e.g. via docker-compose up + .env):
    python seed.py

Idempotent, and run on every deploy. The sample deals live in a template
account (app/demo.py); every new sign-in and every demo visitor gets their own
copy of it the first time they use the app. This script
  1. moves deals from before sign-in (no owner; they were just samples) into
     the template, and
  2. adds any sample deal the template doesn't have yet, matched by name.
It never touches users' own deals, so deleting a sample deal sticks.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.demo import DEMO_TEMPLATE_OWNER
from app.models import Deal
from app.sample_deals import SAMPLE_DEALS


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def main() -> None:
    raw_url = os.environ["DATABASE_URL"]
    database_url = normalize_database_url(raw_url)
    engine = create_engine(database_url)
    with Session(engine) as session:
        moved = (
            session.query(Deal)
            .filter(Deal.owner_id.is_(None))
            .update({Deal.owner_id: DEMO_TEMPLATE_OWNER})
        )
        if moved:
            session.commit()
            print(f"Moved {moved} deals from before sign-in into the template.")

        have = {
            name
            for (name,) in session.query(Deal.name).filter(Deal.owner_id == DEMO_TEMPLATE_OWNER)
        }
        missing = [d for d in SAMPLE_DEALS if d["name"] not in have]
        session.add_all(Deal(**d, owner_id=DEMO_TEMPLATE_OWNER) for d in missing)
        session.commit()
    print(f"Template: {len(missing)} added, {len(SAMPLE_DEALS) - len(missing)} already there.")


if __name__ == "__main__":
    main()

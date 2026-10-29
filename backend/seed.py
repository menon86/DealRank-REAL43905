"""Load the sample deals (app/sample_deals.py).

Usage (with DATABASE_URL set, e.g. via docker-compose up + .env):
    python seed.py

Idempotent, and run on every deploy. It
  1. gives deals from before sign-in (no owner) to SEED_OWNER_EMAIL,
  2. keeps the sample-deal template current (new sign-ins and demo visitors
     get a copy of it, see app/demo.py), adding only names it doesn't have, and
  3. on an empty database, gives SEED_OWNER_EMAIL its own copy of the samples.
Deals you delete are never re-added to an account that already has deals.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.demo import DEMO_TEMPLATE_OWNER
from app.models import Deal
from app.sample_deals import SAMPLE_DEALS

# Who owns the sample deals (a signed-in user's lowercase email).
SEED_OWNER_EMAIL = os.environ.get("SEED_OWNER_EMAIL", "dev@localhost").strip().lower()


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
        # Deals created before sign-in existed have no owner; give them to the seed owner.
        claimed = (
            session.query(Deal)
            .filter(Deal.owner_id.is_(None))
            .update({Deal.owner_id: SEED_OWNER_EMAIL})
        )
        if claimed:
            session.commit()
            print(f"Assigned {claimed} unowned deals to {SEED_OWNER_EMAIL}.")

        template_names = {
            name
            for (name,) in session.query(Deal.name).filter(Deal.owner_id == DEMO_TEMPLATE_OWNER)
        }
        added = [d for d in SAMPLE_DEALS if d["name"] not in template_names]
        session.add_all(Deal(**d, owner_id=DEMO_TEMPLATE_OWNER) for d in added)
        session.commit()
        print(f"Template: {len(added)} added, {len(SAMPLE_DEALS) - len(added)} already there.")

        has_deals = (
            session.query(Deal).filter(Deal.owner_id != DEMO_TEMPLATE_OWNER).first() is not None
        )
        if has_deals:
            print("Deals already exist. Not seeding an owner copy.")
            return
        session.add_all(Deal(**d, owner_id=SEED_OWNER_EMAIL) for d in SAMPLE_DEALS)
        session.commit()
    print(f"Seeded {len(SAMPLE_DEALS)} deals for {SEED_OWNER_EMAIL}.")


if __name__ == "__main__":
    main()

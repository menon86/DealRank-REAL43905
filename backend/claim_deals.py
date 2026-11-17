"""Give every unowned deal to one account.

Deals belong to the user who created them, and each user sees only their
own. Rows from before sign-in existed (and rows written by seed.py) have no
owner, so nobody sees them until they are claimed with this script.

Usage (with DATABASE_URL set):
    python claim_deals.py USERNAME
"""

import sys

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Deal, User


def claim(username: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username.strip().lower()))
        if user is None:
            sys.exit(f"No account named {username!r}. Create it in the app first.")
        result = db.execute(
            update(Deal).where(Deal.owner_id.is_(None)).values(owner_id=str(user.id))
        )
        db.commit()
        return result.rowcount


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(f"Gave {claim(sys.argv[1])} unowned deals to {sys.argv[1]}.")

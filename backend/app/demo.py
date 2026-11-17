"""Starting sample deals, and the demo profile.

Every account starts with its own copy of the template deals (those owned by
DEMO_TEMPLATE_OWNER, loaded by seed.py): `ensure_sample_deals` copies them the
first time a user is seen. "Try the demo" gives a visitor a private, throwaway
account the same way.

Each demo visit mints a fresh owner (demo-<random>@demo.local) holding its own copy
of the template deals, so visitors can edit freely without touching each other's deals. Old demo
accounts are deleted on the next visit.
"""

import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.deal import Deal
from app.models.user_profile import UserProfile

DEMO_DOMAIN = "demo.local"
DEMO_TEMPLATE_OWNER = f"template@{DEMO_DOMAIN}"
DEMO_ISSUER = "dealrank-demo"
DEMO_AUDIENCE = "dealrank-api"
DEMO_RETENTION = timedelta(hours=24)

_NOT_COPIED = {"id", "owner_id", "created_at", "updated_at"}


def is_demo_email(email: str) -> bool:
    return email.endswith(f"@{DEMO_DOMAIN}")


def clone_deal(source: Deal, owner: str) -> Deal:
    # None is skipped so a not-yet-saved source (seed.py) falls back to the column
    # defaults instead of overwriting them with NULL.
    values = {
        attr.key: getattr(source, attr.key)
        for attr in Deal.__mapper__.column_attrs
        if attr.key not in _NOT_COPIED and getattr(source, attr.key) is not None
    }
    return Deal(id=uuid.uuid4(), owner_id=owner, **values)


def purge_old_demo_accounts(db: Session) -> None:
    cutoff = datetime.now(UTC) - DEMO_RETENTION
    db.execute(
        delete(Deal).where(
            Deal.owner_id.like(f"%@{DEMO_DOMAIN}"),
            Deal.owner_id != DEMO_TEMPLATE_OWNER,
            Deal.created_at < cutoff,
        )
    )
    db.execute(
        delete(UserProfile).where(
            UserProfile.email.like(f"%@{DEMO_DOMAIN}"),
            UserProfile.email != DEMO_TEMPLATE_OWNER,
            UserProfile.created_at < cutoff,
        )
    )


def ensure_sample_deals(db: Session, email: str) -> None:
    """On a user's first visit, copies the template deals into their account.

    The profile row is what makes this once-only, so deals a user deletes don't
    come back. A user who already has deals (e.g. the seed owner) gets no copies.
    """
    first_visit = db.execute(
        insert(UserProfile)
        .values(email=email)
        .on_conflict_do_nothing()
        .returning(UserProfile.email)
    ).first()
    if first_visit is not None:
        has_deals = db.scalars(select(Deal.id).where(Deal.owner_id == email).limit(1)).first()
        if has_deals is None:
            template = db.scalars(
                select(Deal).where(Deal.owner_id == DEMO_TEMPLATE_OWNER).order_by(Deal.name)
            ).all()
            db.add_all(clone_deal(deal, email) for deal in template)
    db.commit()


def start_demo(db: Session, settings: Settings) -> tuple[str, str]:
    """Creates a demo account with its own deal copies; returns (token, email)."""
    purge_old_demo_accounts(db)
    email = f"demo-{secrets.token_hex(4)}@{DEMO_DOMAIN}"
    ensure_sample_deals(db, email)
    return issue_demo_token(email, settings), email


def issue_demo_token(email: str, settings: Settings) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": DEMO_ISSUER,
            "aud": DEMO_AUDIENCE,
            "email": email,
            "iat": now,
            "exp": now + settings.DEMO_TOKEN_TTL_MINUTES * 60,
        },
        settings.DEMO_TOKEN_SECRET.get_secret_value(),
        algorithm="HS256",
    )

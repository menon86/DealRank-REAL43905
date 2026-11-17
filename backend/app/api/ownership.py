"""Per-user deal access. Every deal read goes through here so a user can
never load, list, edit, rank, export or chat about someone else's deal; an
unowned id returns the same 404 as a missing one.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.deal import Deal


def owned_deals(owner: str) -> Select[tuple[Deal]]:
    return select(Deal).where(Deal.owner_id == owner)


def get_owned_deal(db: Session, deal_id: uuid.UUID, owner: str) -> Deal | None:
    return db.scalars(owned_deals(owner).where(Deal.id == deal_id)).first()


def get_owned_deal_or_404(db: Session, deal_id: uuid.UUID, owner: str) -> Deal:
    deal = get_owned_deal(db, deal_id, owner)
    if deal is None:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")
    return deal

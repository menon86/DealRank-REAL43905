"""Deal CRUD and per-deal metrics. See docs/build-plan.md 3.2 and 3.3."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.converters import deal_to_engine_inputs
from app.api.schemas import DealBase, DealCreate, DealOut, DealUpdate, MetricsOut
from app.db import get_db
from app.engine.metrics import compute
from app.models.deal import Deal

router = APIRouter(prefix="/deals", tags=["deals"])


def _get_deal_or_404(db: Session, deal_id: uuid.UUID) -> Deal:
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")
    return deal


@router.post("", response_model=DealOut, status_code=201)
def create_deal(payload: DealCreate, db: Session = Depends(get_db)) -> Deal:
    deal = Deal(**payload.model_dump())
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


@router.get("", response_model=list[DealOut])
def list_deals(db: Session = Depends(get_db)) -> list[Deal]:
    return list(db.execute(select(Deal).order_by(Deal.created_at)).scalars())


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(deal_id: uuid.UUID, db: Session = Depends(get_db)) -> Deal:
    return _get_deal_or_404(db, deal_id)


@router.patch("/{deal_id}", response_model=DealOut)
def update_deal(deal_id: uuid.UUID, payload: DealUpdate, db: Session = Depends(get_db)) -> Deal:
    deal = _get_deal_or_404(db, deal_id)

    updates = payload.model_dump(exclude_unset=True)

    # Validate the merged row (existing fields + this patch) against the
    # same leasing-mode/branch rule DealCreate enforces, so a PATCH can't
    # leave a deal in a state POST would have rejected with a 422.
    merged = {field: updates.get(field, getattr(deal, field)) for field in DealBase.model_fields}
    try:
        DealBase(**merged)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    for field, value in updates.items():
        setattr(deal, field, value)

    db.commit()
    db.refresh(deal)
    return deal


@router.delete("/{deal_id}", status_code=204)
def delete_deal(deal_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    deal = _get_deal_or_404(db, deal_id)
    db.delete(deal)
    db.commit()


@router.get("/{deal_id}/metrics", response_model=MetricsOut)
def get_deal_metrics(deal_id: uuid.UUID, db: Session = Depends(get_db)) -> MetricsOut:
    deal = _get_deal_or_404(db, deal_id)
    inputs = deal_to_engine_inputs(deal)
    return compute(inputs)

"""Rent sanity check against loaded Zillow / Apartment List CSV data."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.analysis_schemas import GeographyOut, RentCheckOut
from app.api.ownership import get_owned_deal_or_404
from app.auth import current_owner
from app.db import get_db
from app.models.market_rent import MarketRent
from app.services.market_rents import check_rent

router = APIRouter(tags=["market-check"])


@router.get("/market-rents/geographies", response_model=list[GeographyOut])
def geographies(db: Session = Depends(get_db)) -> list[GeographyOut]:
    rows = db.execute(
        select(MarketRent.geography, MarketRent.source, func.max(MarketRent.period))
        .group_by(MarketRent.geography, MarketRent.source)
        .order_by(MarketRent.geography)
    ).all()
    return [GeographyOut(geography=g, source=s, latest_period=p) for g, s, p in rows]


@router.get("/deals/{deal_id}/rent-check", response_model=RentCheckOut)
def rent_check(
    deal_id: uuid.UUID,
    geography: str = Query(min_length=1),
    source: str | None = None,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> RentCheckOut:
    deal = get_owned_deal_or_404(db, deal_id, owner)
    result = check_rent(db, geography, per_unit_rent=deal.monthly_rent_per_unit, source=source)
    return RentCheckOut(
        status=result.status,
        geography=geography,
        deal_rent=result.deal_rent,
        market_rent=result.market_rent,
        market_period=result.market_period,
        source=result.source,
        variance=result.variance,
        market_yoy_growth=result.market_yoy_growth,
        deal_rent_growth=deal.rent_growth_rate,
        note=result.note,
    )

"""Rent sanity check against loaded Zillow / Apartment List CSV data."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.analysis_schemas import GeographyOut, RentCheckOut, RentUploadOut
from app.db import get_db
from app.models.deal import Deal
from app.models.market_rent import MarketRent
from app.services.market_rents import ALL_CLASSES, check_rent, load_rows, parse_wide_rent_csv

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
) -> RentCheckOut:
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")
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


MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("/market-rents/upload", response_model=RentUploadOut)
async def upload_market_rents(
    request: Request,
    source: Literal["zillow_zori", "apartment_list"],
    months: int = Query(default=24, ge=1, le=120),
    db: Session = Depends(get_db),
) -> RentUploadOut:
    """Loads a Zillow ZORI or Apartment List CSV sent as the raw request body
    (Content-Type: text/csv). Same parser and idempotent upsert as
    ingest_market_rents.py, so re-uploading a refreshed file is safe.
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV is larger than 25 MB.")
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV is larger than 25 MB.")
    try:
        rows = parse_wide_rent_csv(raw.decode("utf-8-sig"), months)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="File must be UTF-8 CSV text.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=422, detail="No rent values found in the file.")
    inserted, updated = load_rows(db, source, rows, ALL_CLASSES)
    db.commit()
    return RentUploadOut(
        source=source,
        inserted=inserted,
        updated=updated,
        geographies=len({r.geography for r in rows}),
    )

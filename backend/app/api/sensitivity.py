"""POST /deals/{id}/sensitivity (single-variable sweep) and
POST /deals/{id}/monte-carlo. Both re-run the real engine; neither is
persisted.
"""

import secrets
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.analysis_schemas import (
    DistributionOut,
    HistogramBinOut,
    MonteCarloRequest,
    MonteCarloResponse,
    SweepPointOut,
    SweepRequest,
    SweepResponse,
)
from app.api.converters import deal_to_engine_inputs
from app.api.risk_rank import build_hurdle, latest_spread
from app.db import get_db
from app.engine import sensitivity
from app.models.deal import Deal
from app.services.treasury import get_treasury_10y

router = APIRouter(tags=["sensitivity"])

# Default sweep window around the deal's own value.
DEFAULT_SPAN = {"exit_cap_rate": Decimal("0.015"), "rent_growth_rate": Decimal("0.03")}


def _load(db: Session, deal_id: uuid.UUID) -> Deal:
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")
    return deal


@router.post("/deals/{deal_id}/sensitivity", response_model=SweepResponse)
def sweep(
    deal_id: uuid.UUID, payload: SweepRequest, db: Session = Depends(get_db)
) -> SweepResponse:
    deal = _load(db, deal_id)
    inputs = deal_to_engine_inputs(deal)
    base = getattr(inputs, payload.variable)
    span = DEFAULT_SPAN[payload.variable]
    low = payload.low if payload.low is not None else base - span
    high = payload.high if payload.high is not None else base + span
    if payload.variable == "exit_cap_rate":
        low = max(low, Decimal("0.01"))
    try:
        points = sensitivity.sweep(inputs, payload.variable, low, high, payload.steps)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SweepResponse(
        variable=payload.variable,
        base_value=base,
        points=[SweepPointOut(**vars(p)) for p in points],
    )


@router.post("/deals/{deal_id}/monte-carlo", response_model=MonteCarloResponse)
def monte_carlo(
    deal_id: uuid.UUID, payload: MonteCarloRequest, db: Session = Depends(get_db)
) -> MonteCarloResponse:
    deal = _load(db, deal_id)
    inputs = deal_to_engine_inputs(deal)

    if payload.hurdle is not None:
        hurdle, hurdle_source = payload.hurdle, "user"
    else:
        h = build_hurdle(latest_spread(db, deal.sub_asset_class.value), get_treasury_10y())
        hurdle, hurdle_source = h.total, "risk_adjusted"

    seed = payload.seed if payload.seed is not None else secrets.randbelow(2**31)
    spec = sensitivity.MonteCarloSpec(
        exit_cap_sd=payload.exit_cap_sd,
        rent_growth_sd=payload.rent_growth_sd,
        vacancy_sd=payload.vacancy_sd,
        exit_cap_rent_growth_correlation=payload.exit_cap_rent_growth_correlation,
        simulations=payload.simulations,
        seed=seed,
    )
    result = sensitivity.monte_carlo(
        inputs,
        spec,
        hurdle=hurdle,
        dscr_minimum=payload.dscr_minimum,
        hurdle_on_gross_irr=hurdle_source == "risk_adjusted",
    )

    def dist(d):
        return DistributionOut(**vars(d)) if d else None

    return MonteCarloResponse(
        simulations=result.simulations,
        converged=result.converged,
        levered_converged=result.levered_converged,
        seed=seed,
        hurdle=hurdle,
        hurdle_source=hurdle_source,
        unlevered_irr=dist(result.unlevered_irr),
        levered_irr=dist(result.levered_irr),
        unlevered_irr_before_costs=dist(result.unlevered_irr_before_costs),
        hurdle_basis="before_costs" if hurdle_source == "risk_adjusted" else "after_costs",
        unlevered_histogram=[HistogramBinOut(**vars(b)) for b in result.unlevered_histogram],
        prob_below_hurdle=result.prob_below_hurdle,
        prob_dscr_below_minimum=result.prob_dscr_below_minimum,
    )

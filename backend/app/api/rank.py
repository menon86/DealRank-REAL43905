"""POST /rank. See docs/build-plan.md 3.4.

D2's hurdle is one flat user-entered rate across all sub-classes; per
app/engine/ranking.py's docstring this stays inline here rather than in
that module, because it has no sub-class-specific behavior yet to
justify a module of its own.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.converters import deal_to_engine_inputs
from app.api.schemas import MetricsOut, RankedDealOut, RankRequest
from app.db import get_db
from app.engine.metrics import compute
from app.models.deal import Deal

router = APIRouter(tags=["rank"])

# A deal whose unlevered IRR didn't converge (see app/engine/metrics.py)
# sorts last rather than disappearing from the ranking — the DSCR gate
# that would exclude a deal entirely is Deliverable 3, not D2 (see
# docs/build-plan.md Phase 4).
_NON_CONVERGING_SPREAD = Decimal("-Infinity")


@router.post("/rank", response_model=list[RankedDealOut])
def rank_deals(payload: RankRequest, db: Session = Depends(get_db)) -> list[RankedDealOut]:
    ranked: list[tuple[Deal, MetricsOut, Decimal]] = []

    for deal_id in payload.deal_ids:
        deal = db.get(Deal, deal_id)
        if deal is None:
            raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

        inputs = deal_to_engine_inputs(deal)
        engine_metrics = compute(inputs)
        metrics = MetricsOut.model_validate(engine_metrics)

        spread = (
            _NON_CONVERGING_SPREAD
            if metrics.unlevered_irr is None
            else metrics.unlevered_irr - payload.hurdle_rate
        )
        ranked.append((deal, metrics, spread))

    ranked.sort(key=lambda entry: entry[2], reverse=True)

    return [
        RankedDealOut(deal=deal, metrics=metrics, spread=spread, rank=index + 1)
        for index, (deal, metrics, spread) in enumerate(ranked)
    ]

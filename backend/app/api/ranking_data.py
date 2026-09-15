"""Shared ranking computation, used by both POST /rank (app/api/rank.py)
and the PDF/PPTX export routes (app/api/reports.py) — one place computes
and sorts the ranking so the exported reports can't drift from what the
ranking view actually shows.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.converters import deal_to_engine_inputs
from app.engine.metrics import compute
from app.engine.types import DealMetrics
from app.models.deal import Deal

# A deal whose unlevered IRR didn't converge (see app/engine/metrics.py)
# sorts last rather than disappearing from the ranking — the DSCR gate
# that would exclude a deal entirely is Deliverable 3, not D2 (see
# docs/build-plan.md Phase 4).
NON_CONVERGING_SPREAD = Decimal("-Infinity")

RANKING_BASIS_NOTE = (
    "Ranked by unlevered IRR minus the supplied hurdle rate, descending. "
    "Levered IRR is included for reference only and is never sorted on."
)


@dataclass(frozen=True)
class RankedEntry:
    deal: Deal
    metrics: DealMetrics
    spread: Decimal
    rank: int


def gather_ranked_entries(
    db: Session, deal_ids: list[uuid.UUID], hurdle_rate: Decimal
) -> list[RankedEntry]:
    """Loads each deal, computes its metrics, and returns them sorted by
    unlevered IRR minus hurdle_rate, descending, with rank assigned.
    Raises HTTPException(404) naming the first unknown deal id.
    """
    unranked: list[tuple[Deal, DealMetrics, Decimal]] = []

    for deal_id in deal_ids:
        deal = db.get(Deal, deal_id)
        if deal is None:
            raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

        metrics = compute(deal_to_engine_inputs(deal))
        spread = (
            NON_CONVERGING_SPREAD
            if metrics.unlevered_irr is None
            else metrics.unlevered_irr - hurdle_rate
        )
        unranked.append((deal, metrics, spread))

    unranked.sort(key=lambda entry: entry[2], reverse=True)

    return [
        RankedEntry(deal=deal, metrics=metrics, spread=spread, rank=index + 1)
        for index, (deal, metrics, spread) in enumerate(unranked)
    ]

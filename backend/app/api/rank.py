"""POST /rank. See docs/build-plan.md 3.4.

D2's hurdle is one flat user-entered rate across all sub-classes; per
app/engine/ranking.py's docstring this stays inline here rather than in
that module, because it has no sub-class-specific behavior yet to
justify a module of its own.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.ranking_data import gather_ranked_entries
from app.api.schemas import MetricsOut, RankedDealOut, RankRequest
from app.db import get_db

router = APIRouter(tags=["rank"])


@router.post("/rank", response_model=list[RankedDealOut])
def rank_deals(payload: RankRequest, db: Session = Depends(get_db)) -> list[RankedDealOut]:
    entries = gather_ranked_entries(db, payload.deal_ids, payload.hurdle_rate)
    return [
        RankedDealOut(
            deal=entry.deal,
            metrics=MetricsOut.model_validate(entry.metrics),
            spread=entry.spread,
            rank=entry.rank,
        )
        for entry in entries
    ]

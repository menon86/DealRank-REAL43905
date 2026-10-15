"""Risk-adjusted ranking: GET /reference/hurdles, POST /rank/risk-adjusted.

Each deal is ranked on unlevered IRR minus *its own sub-class's* hurdle
(10-Year Treasury + survey cap-rate spread + stabilized NOI growth), after
a DSCR gate removes under-covered deals. Optional preference weights then
blend return, cash flow and safety. See app/engine/ranking.py.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.analysis_schemas import (
    ExcludedDealOut,
    FactorScoresOut,
    HurdleOut,
    HurdleTableOut,
    RiskRankedDealOut,
    RiskRankRequest,
    RiskRankResponse,
    TreasuryOut,
    WeightsOut,
)
from app.api.converters import deal_to_engine_inputs
from app.api.schemas import MetricsOut
from app.db import get_db
from app.engine.metrics import compute
from app.engine.ranking import (
    RETURN_ONLY,
    Candidate,
    RiskAdjustedHurdle,
    Weights,
    passes_dscr_gate,
    questionnaire_to_weights,
    score_candidates,
)
from app.models.cap_rate_spread import CapRateSpread
from app.models.deal import Deal
from app.services.treasury import TreasuryQuote, get_treasury_10y, override_quote

router = APIRouter(tags=["risk-adjusted-ranking"])

BASIS_NOTE = (
    "Ranked on unlevered IRR minus each deal's own risk-adjusted hurdle "
    "(10-Year Treasury + sub-class cap-rate spread + stabilized NOI growth). "
    "Deals below the DSCR minimum are excluded, not penalized. Levered IRR is "
    "reference only and is never sorted on."
)


def latest_spread(db: Session, sub_asset_class: str) -> CapRateSpread:
    row = db.scalars(
        select(CapRateSpread)
        .where(CapRateSpread.sub_asset_class == sub_asset_class)
        .order_by(CapRateSpread.effective_date.desc())
        .limit(1)
    ).first()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No cap-rate spread loaded for '{sub_asset_class}'. "
                "Run seed_reference_data.py to load the reference table."
            ),
        )
    return row


def build_hurdle(spread: CapRateSpread, treasury: TreasuryQuote) -> HurdleOut:
    h = RiskAdjustedHurdle(
        treasury_yield=treasury.yield_,
        spread_bps=spread.spread_bps,
        noi_growth=Decimal(spread.assumed_stabilized_noi_growth),
    )
    return HurdleOut(
        sub_asset_class=spread.sub_asset_class,
        treasury_yield=h.treasury_yield,
        spread_bps=h.spread_bps,
        cap_rate=h.cap_rate,
        noi_growth=h.noi_growth,
        total=h.total,
        survey_source=spread.survey_source,
        survey_quarter=spread.survey_quarter,
        effective_date=spread.effective_date,
    )


def treasury_out(q: TreasuryQuote) -> TreasuryOut:
    return TreasuryOut(yield_=q.yield_, as_of=q.as_of, source=q.source)


@router.get("/reference/hurdles", response_model=HurdleTableOut, response_model_by_alias=True)
def hurdle_table(db: Session = Depends(get_db)) -> HurdleTableOut:
    treasury = get_treasury_10y()
    classes = sorted(set(db.scalars(select(CapRateSpread.sub_asset_class))))
    return HurdleTableOut(
        treasury=treasury_out(treasury),
        hurdles=[build_hurdle(latest_spread(db, c), treasury) for c in classes],
    )


def _resolve_weights(payload: RiskRankRequest) -> Weights:
    if payload.weights is not None:
        w = payload.weights
        return Weights(w.irr, w.cash_flow, w.risk).normalized()
    if payload.answers is not None:
        a = payload.answers
        return questionnaire_to_weights(a.primary_goal, a.risk_tolerance, a.income_need)
    return RETURN_ONLY


@router.post("/rank/risk-adjusted", response_model=RiskRankResponse, response_model_by_alias=True)
def rank_risk_adjusted(payload: RiskRankRequest, db: Session = Depends(get_db)) -> RiskRankResponse:
    treasury = (
        override_quote(payload.treasury_yield)
        if payload.treasury_yield is not None
        else get_treasury_10y()
    )
    weights = _resolve_weights(payload)

    evaluated = []
    for deal_id in payload.deal_ids:
        deal = db.get(Deal, deal_id)
        if deal is None:
            raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")
        metrics = compute(deal_to_engine_inputs(deal))
        hurdle = build_hurdle(latest_spread(db, deal.sub_asset_class.value), treasury)
        evaluated.append((deal, metrics, hurdle))

    excluded: list[ExcludedDealOut] = []
    candidates: list[Candidate] = []
    kept = {}
    for deal, metrics, hurdle in evaluated:
        reason = None
        if not passes_dscr_gate(metrics.year_one_dscr, payload.dscr_minimum):
            reason = (
                f"Year-one DSCR {metrics.year_one_dscr:.2f}x is below the "
                f"{payload.dscr_minimum:.2f}x minimum."
            )
        elif metrics.unlevered_irr is None:
            reason = "Unlevered IRR did not converge."
        if reason:
            excluded.append(
                ExcludedDealOut(
                    deal=deal,
                    metrics=MetricsOut.model_validate(metrics),
                    hurdle=hurdle,
                    reason=reason,
                )
            )
            continue
        spread = metrics.unlevered_irr - hurdle.total
        key = str(deal.id)
        kept[key] = (deal, metrics, hurdle, spread)
        candidates.append(
            Candidate(
                key=key,
                spread=spread,
                cash_on_cash=metrics.cash_on_cash,
                year_one_dscr=metrics.year_one_dscr,
                ltv=deal.loan_amount / deal.purchase_price,
            )
        )

    scored = score_candidates(candidates, weights)
    # Higher score first; spread breaks ties so equal scores are still ordered.
    scored.sort(key=lambda s: (s.score, kept[s.key][3]), reverse=True)

    ranked = []
    for index, s in enumerate(scored):
        deal, metrics, hurdle, spread = kept[s.key]
        ranked.append(
            RiskRankedDealOut(
                rank=index + 1,
                deal=deal,
                metrics=MetricsOut.model_validate(metrics),
                hurdle=hurdle,
                spread=spread,
                ltv=deal.loan_amount / deal.purchase_price,
                factors=FactorScoresOut(
                    irr=s.factors.irr, cash_flow=s.factors.cash_flow, risk=s.factors.risk
                ),
                score=s.score,
            )
        )

    return RiskRankResponse(
        treasury=treasury_out(treasury),
        dscr_minimum=payload.dscr_minimum,
        weights=WeightsOut(irr=weights.irr, cash_flow=weights.cash_flow, risk=weights.risk),
        ranked=ranked,
        excluded=excluded,
        basis_note=BASIS_NOTE,
    )

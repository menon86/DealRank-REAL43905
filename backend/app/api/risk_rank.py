"""Risk-adjusted ranking: GET /reference/hurdles, POST /rank/risk-adjusted.

Each deal is ranked on unlevered IRR minus *its own sub-class's* hurdle
(10-Year Treasury + survey cap-rate spread + stabilized NOI growth), after
a DSCR gate removes under-covered deals. Optional preference weights then
blend return, cash flow and safety. See app/engine/ranking.py.
"""

from dataclasses import dataclass
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
    FactorScores,
    RiskAdjustedHurdle,
    Weights,
    passes_debt_yield_gate,
    passes_dscr_gate,
    questionnaire_to_weights,
    score_candidates,
)
from app.engine.types import DealMetrics
from app.models.cap_rate_spread import CapRateSpread
from app.models.deal import Deal
from app.services.treasury import TreasuryQuote, get_treasury_10y, override_quote

router = APIRouter(tags=["risk-adjusted-ranking"])

BASIS_NOTE = (
    "Ranked on unlevered IRR (before closing and selling costs, the basis the "
    "hurdle is quoted on) minus each deal's own risk-adjusted hurdle "
    "(10-Year Treasury + sub-class cap-rate spread + stabilized NOI growth). "
    "Deals below the DSCR minimum (lowest DSCR over the hold) are excluded, "
    "not penalized. Levered IRR is reference only and is never sorted on."
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


RENT_GROWTH_TOLERANCE = Decimal("0.01")


def _warnings(deal: Deal, metrics, hurdle: HurdleOut) -> list[str]:
    """Assumptions that flatter the return without being an error."""
    warnings = []
    if deal.exit_cap_rate < metrics.going_in_cap_rate:
        warnings.append(
            f"Exit cap {deal.exit_cap_rate * 100:.2f}% is below the going-in cap "
            f"{metrics.going_in_cap_rate * 100:.2f}%: the return leans on cap-rate compression."
        )
    if deal.rent_growth_rate > hurdle.noi_growth + RENT_GROWTH_TOLERANCE:
        warnings.append(
            f"Rent growth {deal.rent_growth_rate * 100:.2f}% is well above the "
            f"{hurdle.noi_growth * 100:.2f}% stabilized growth the hurdle assumes."
        )
    return warnings


@dataclass(frozen=True)
class RankedRow:
    rank: int
    deal: Deal
    metrics: DealMetrics
    hurdle: HurdleOut
    spread: Decimal
    ltv: Decimal
    warnings: list[str]
    factors: FactorScores
    score: Decimal


@dataclass(frozen=True)
class ExcludedRow:
    deal: Deal
    metrics: DealMetrics
    hurdle: HurdleOut
    reason: str
    # Unlevered IRR before costs minus the hurdle; None if the IRR didn't converge.
    spread: Decimal | None = None


@dataclass(frozen=True)
class RiskRanking:
    """The risk-adjusted ranking with the ORM deals and engine metrics
    still attached, so the API response and the PDF/PPTX reports are built
    from one computation and cannot disagree.
    """

    treasury: TreasuryQuote
    dscr_minimum: Decimal
    debt_yield_minimum: Decimal | None
    weights: Weights
    ranked: list[RankedRow]
    excluded: list[ExcludedRow]


def compute_risk_ranking(db: Session, payload: RiskRankRequest) -> RiskRanking:
    treasury = (
        override_quote(payload.treasury_yield)
        if payload.treasury_yield is not None
        else get_treasury_10y()
    )
    weights = _resolve_weights(payload)

    evaluated = []
    for deal_id in dict.fromkeys(payload.deal_ids):
        deal = db.get(Deal, deal_id)
        if deal is None:
            raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")
        metrics = compute(deal_to_engine_inputs(deal))
        hurdle = build_hurdle(latest_spread(db, deal.sub_asset_class.value), treasury)
        evaluated.append((deal, metrics, hurdle))

    excluded: list[ExcludedRow] = []
    candidates: list[Candidate] = []
    kept = {}
    for deal, metrics, hurdle in evaluated:
        reason = None
        if not passes_dscr_gate(metrics.min_dscr, payload.dscr_minimum):
            reason = (
                f"Lowest DSCR over the hold ({metrics.min_dscr:.2f}x) is below the "
                f"{payload.dscr_minimum:.2f}x minimum."
            )
        elif not passes_debt_yield_gate(metrics.debt_yield, payload.debt_yield_minimum):
            reason = (
                f"Debt yield {metrics.debt_yield * 100:.2f}% is below the "
                f"{payload.debt_yield_minimum * 100:.2f}% minimum."
            )
        elif metrics.unlevered_irr_before_costs is None:
            reason = "Unlevered IRR did not converge."
        if reason:
            gross_irr = metrics.unlevered_irr_before_costs
            excluded.append(
                ExcludedRow(
                    deal=deal,
                    metrics=metrics,
                    hurdle=hurdle,
                    reason=reason,
                    spread=None if gross_irr is None else gross_irr - hurdle.total,
                )
            )
            continue
        spread = metrics.unlevered_irr_before_costs - hurdle.total
        key = str(deal.id)
        kept[key] = (deal, metrics, hurdle, spread)
        candidates.append(
            Candidate(
                key=key,
                spread=spread,
                cash_yield=metrics.unlevered_cash_yield,
                min_dscr=metrics.min_dscr,
                leverage=(metrics.total_debt + metrics.preferred_equity) / deal.purchase_price,
            )
        )

    scored = score_candidates(candidates, weights)
    # Higher score first; spread breaks ties so equal scores are still ordered.
    scored.sort(key=lambda s: (s.score, kept[s.key][3]), reverse=True)

    ranked = []
    for index, s in enumerate(scored):
        deal, metrics, hurdle, spread = kept[s.key]
        ranked.append(
            RankedRow(
                rank=index + 1,
                deal=deal,
                metrics=metrics,
                hurdle=hurdle,
                spread=spread,
                ltv=metrics.total_debt / deal.purchase_price,
                warnings=_warnings(deal, metrics, hurdle),
                factors=s.factors,
                score=s.score,
            )
        )

    return RiskRanking(
        treasury=treasury,
        dscr_minimum=payload.dscr_minimum,
        debt_yield_minimum=payload.debt_yield_minimum,
        weights=weights,
        ranked=ranked,
        excluded=excluded,
    )


@router.post("/rank/risk-adjusted", response_model=RiskRankResponse, response_model_by_alias=True)
def rank_risk_adjusted(payload: RiskRankRequest, db: Session = Depends(get_db)) -> RiskRankResponse:
    result = compute_risk_ranking(db, payload)
    return RiskRankResponse(
        treasury=treasury_out(result.treasury),
        dscr_minimum=result.dscr_minimum,
        debt_yield_minimum=result.debt_yield_minimum,
        weights=WeightsOut(
            irr=result.weights.irr, cash_flow=result.weights.cash_flow, risk=result.weights.risk
        ),
        ranked=[
            RiskRankedDealOut(
                rank=r.rank,
                deal=r.deal,
                metrics=MetricsOut.model_validate(r.metrics),
                hurdle=r.hurdle,
                spread=r.spread,
                ltv=r.ltv,
                warnings=r.warnings,
                factors=FactorScoresOut(
                    irr=r.factors.irr, cash_flow=r.factors.cash_flow, risk=r.factors.risk
                ),
                score=r.score,
            )
            for r in result.ranked
        ],
        excluded=[
            ExcludedDealOut(
                deal=e.deal,
                metrics=MetricsOut.model_validate(e.metrics),
                hurdle=e.hurdle,
                reason=e.reason,
                spread=e.spread,
            )
            for e in result.excluded
        ],
        basis_note=BASIS_NOTE,
    )

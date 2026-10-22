"""GET /reports/pdf and GET /reports/pptx. See docs/build-plan.md 6.2-6.3.

By default the reports show the risk-adjusted ranking, computed by the same
function as POST /rank/risk-adjusted, so an export always matches the
ranking view. Passing `hurdle_rate` instead produces the original
flat-hurdle report.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.analysis_schemas import QuestionnaireIn, RiskRankRequest, WeightsIn
from app.api.ranking_data import gather_ranked_entries
from app.api.risk_rank import compute_risk_ranking
from app.db import get_db
from app.engine.ranking import DEFAULT_DSCR_MINIMUM
from app.reports.data import ReportData, flat_report, risk_report
from app.reports.pdf import build_pdf_bytes
from app.reports.pptx import build_pptx_bytes

router = APIRouter(prefix="/reports", tags=["reports"])

PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _report_data(
    db: Session,
    deal_ids: list[uuid.UUID],
    hurdle_rate: Decimal | None,
    treasury_yield: Decimal | None,
    dscr_minimum: Decimal,
    debt_yield_minimum: Decimal | None,
    primary_goal: str | None,
    risk_tolerance: int | None,
    income_need: int | None,
    weight_irr: Decimal | None,
    weight_cash_flow: Decimal | None,
    weight_risk: Decimal | None,
) -> ReportData:
    if hurdle_rate is not None:
        return flat_report(gather_ranked_entries(db, deal_ids, hurdle_rate), hurdle_rate)

    weights = None
    answers = None
    if weight_irr is not None or weight_cash_flow is not None or weight_risk is not None:
        try:
            weights = WeightsIn(
                irr=weight_irr or Decimal(0),
                cash_flow=weight_cash_flow or Decimal(0),
                risk=weight_risk or Decimal(0),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif primary_goal is not None:
        try:
            answers = QuestionnaireIn(
                primary_goal=primary_goal,  # type: ignore[arg-type]
                risk_tolerance=risk_tolerance or 3,
                income_need=income_need or 3,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    request = RiskRankRequest(
        deal_ids=deal_ids,
        dscr_minimum=dscr_minimum,
        debt_yield_minimum=debt_yield_minimum,
        treasury_yield=treasury_yield,
        weights=weights,
        answers=answers,
    )
    return risk_report(compute_risk_ranking(db, request))


def _params(
    deal_ids: list[uuid.UUID] = Query(..., min_length=1, max_length=25),
    hurdle_rate: Decimal | None = Query(None, ge=-1, le=1),
    treasury_yield: Decimal | None = Query(None, ge=0, le=1),
    dscr_minimum: Decimal = Query(DEFAULT_DSCR_MINIMUM, ge=0, le=5),
    debt_yield_minimum: Decimal | None = Query(None, ge=0, le=1),
    primary_goal: str | None = Query(None),
    risk_tolerance: int | None = Query(None, ge=1, le=5),
    income_need: int | None = Query(None, ge=1, le=5),
    weight_irr: Decimal | None = Query(None, ge=0),
    weight_cash_flow: Decimal | None = Query(None, ge=0),
    weight_risk: Decimal | None = Query(None, ge=0),
    db: Session = Depends(get_db),
) -> ReportData:
    return _report_data(
        db,
        deal_ids,
        hurdle_rate,
        treasury_yield,
        dscr_minimum,
        debt_yield_minimum,
        primary_goal,
        risk_tolerance,
        income_need,
        weight_irr,
        weight_cash_flow,
        weight_risk,
    )


@router.get("/pdf")
def get_pdf_report(data: ReportData = Depends(_params)) -> Response:
    return Response(
        content=build_pdf_bytes(data),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="dealrank-comparison.pdf"'},
    )


@router.get("/pptx")
def get_pptx_report(data: ReportData = Depends(_params)) -> Response:
    return Response(
        content=build_pptx_bytes(data),
        media_type=PPTX_TYPE,
        headers={"Content-Disposition": 'attachment; filename="dealrank-comparison.pptx"'},
    )

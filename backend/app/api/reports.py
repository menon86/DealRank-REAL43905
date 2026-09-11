"""GET /reports/pdf and GET /reports/pptx. See docs/build-plan.md 6.2-6.3."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.ranking_data import gather_ranked_entries
from app.db import get_db
from app.reports.pdf import build_pdf_bytes
from app.reports.pptx import build_pptx_bytes

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/pdf")
def get_pdf_report(
    deal_ids: list[uuid.UUID] = Query(...),
    hurdle_rate: Decimal = Query(...),
    db: Session = Depends(get_db),
) -> Response:
    entries = gather_ranked_entries(db, deal_ids, hurdle_rate)
    pdf_bytes = build_pdf_bytes(entries, hurdle_rate)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="dealrank-comparison.pdf"'},
    )


@router.get("/pptx")
def get_pptx_report(
    deal_ids: list[uuid.UUID] = Query(...),
    hurdle_rate: Decimal = Query(...),
    db: Session = Depends(get_db),
) -> Response:
    entries = gather_ranked_entries(db, deal_ids, hurdle_rate)
    pptx_bytes = build_pptx_bytes(entries, hurdle_rate)
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": 'attachment; filename="dealrank-comparison.pptx"'},
    )

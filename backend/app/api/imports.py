"""Spreadsheet import. See docs/templates/underwriting-and-financing-import-spec.md.

  GET  /deals/import/template  the formatted .xlsx underwriting template
  POST /deals/import           read an uploaded workbook (the template or the
                               user's own) and return what was found, cell by
                               cell, for the user to confirm

Import never creates or changes a deal: the frontend fills the deal form
from the confirmed values and the normal POST /deals validation applies.
"""

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from app.spreadsheet.matcher import build_proposal
from app.spreadsheet.reader import MAX_BYTES, SpreadsheetError, load_sheets
from app.spreadsheet.schemas import ImportProposal
from app.spreadsheet.template import FILENAME, XLSX_TYPE, build_template_bytes

router = APIRouter(prefix="/deals/import", tags=["import"])


@router.get("/template")
def download_template() -> Response:
    return Response(
        content=build_template_bytes(),
        media_type=XLSX_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{FILENAME}"'},
    )


@router.post("", response_model=ImportProposal)
async def import_spreadsheet(file: UploadFile = File(...)) -> ImportProposal:
    # Read one byte past the limit so an oversized upload is caught without
    # buffering all of it.
    data = await file.read(MAX_BYTES + 1)
    filename = file.filename or "upload"
    try:
        sheets = load_sheets(filename, data)
    except SpreadsheetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return build_proposal(filename, sheets)

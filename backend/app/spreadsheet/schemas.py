"""Response shape of POST /deals/import: a proposal the user reviews.

Nothing is saved. The frontend shows each field with the cell it came from,
lets the user change the value or pick another cell, and only then fills
the deal form.
"""

from typing import Literal

from pydantic import BaseModel

Confidence = Literal["high", "medium"]


class SourceOut(BaseModel):
    sheet: str
    cell: str  # the value's cell, e.g. "B7"
    label: str  # the text the value was found next to


class ChoiceOut(BaseModel):
    value: str
    label: str


class FieldOut(BaseModel):
    key: str
    label: str
    section: Literal["property", "ancillary", "financing"]
    group: str
    kind: Literal["money", "percent", "integer", "number", "text", "choice"]
    unit: str
    choices: list[ChoiceOut]
    # In the form's units: percents are whole numbers ("5.75" = 5.75%).
    value: str | None
    source: SourceOut | None
    candidate_id: str | None
    confidence: Confidence | None
    note: str | None


class CandidateOut(BaseModel):
    """A label with a value beside it, anywhere in the workbook, so the user
    can point a field at a cell the matcher didn't pick."""

    id: str  # "Sheet!B7", the value's address
    sheet: str
    cell: str
    label: str
    text: str
    number: str | None
    # The value read as a whole-number percent (0.05 or a 5% cell -> "5").
    percent: str | None


class MixCellOut(BaseModel):
    text: str
    number: str | None


class MixColumnOut(BaseModel):
    index: int  # position in each row's cells
    letter: str
    header: str


class MixRowOut(BaseModel):
    row: int
    cells: list[MixCellOut]


class UnitMixOut(BaseModel):
    sheet: str
    header_row: int
    columns: list[MixColumnOut]
    rows: list[MixRowOut]
    # Unit mix attribute (name, units, bedsPerUnit, avgSqFt, rent) -> column
    # index, or None when no column was recognized for it.
    mapping: dict[str, int | None]


class ImportProposal(BaseModel):
    filename: str
    sheets: list[str]
    fields: list[FieldOut]
    candidates: list[CandidateOut]
    unit_mix: UnitMixOut | None
    warnings: list[str]

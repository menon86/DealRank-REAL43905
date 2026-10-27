"""Finds deal inputs in a workbook that isn't necessarily in the template layout.

Two passes over every sheet:

1. Unit mix table: a header row naming at least two of units / beds /
   square feet / rent (e.g. "Floor Plan | # Units | Avg SF | Market Rent"),
   read down to the first blank or total row.
2. Label/value pairs: a text cell whose label matches a field's synonyms,
   with the value in the first filled cell to its right (or, failing that,
   directly below). Each field takes its best-scoring label and each cell is
   used once, so "Mezzanine interest rate" goes to the mezzanine field
   rather than the senior rate.

The result is a proposal for the user to confirm, not a deal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from openpyxl.utils import get_column_letter

from app.spreadsheet.fields import FIELDS, UNIT_MIX_COLUMNS, Choice, FieldSpec
from app.spreadsheet.reader import (
    Cell,
    Sheet,
    format_decimal,
    has_percent_sign,
    parse_number,
)
from app.spreadsheet.schemas import (
    CandidateOut,
    ChoiceOut,
    FieldOut,
    ImportProposal,
    MixCellOut,
    MixColumnOut,
    MixRowOut,
    SourceOut,
    UnitMixOut,
)

MAX_LABEL_CHARS = 80
MAX_LABEL_WORDS = 8
MAX_CANDIDATES = 500
MAX_MIX_ROWS = 60
VALUE_LOOKAHEAD = 6
TEXT_LOOKAHEAD = 2
# The template's own non-input tabs, and common equivalents.
SKIPPED_SHEETS = {"instructions", "lists", "read me", "readme", "how to use"}

# A label like "Price per unit" isn't the purchase price.
_PER_QUALIFIERS = ("per unit", "per bed", "per sf", "per sq ft", "psf", "per door", "per key")
_UNIT_WORDS = {
    "year",
    "years",
    "yr",
    "yrs",
    "month",
    "months",
    "mo",
    "bps",
    "usd",
    "pct",
    "percent",
}
_YEAR_WORDS = {"year", "years", "yr", "yrs"}
_SUMMARY_ROW = re.compile(r"^(total|totals|average|avg|weighted|subtotal|sum)\b")


def normalize(text: str) -> str:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = text.lower().replace("&", " and ").replace("#", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def label_score(label: str, synonym: str) -> float:
    """3 for an exact match, about 2 when the synonym's words appear in the
    label (longer synonyms win), 0 otherwise. Single-word synonyms only
    match exactly: "Cap rate" mustn't match "rate"."""
    if not synonym:
        return 0.0
    if label == synonym:
        return 3.0
    syn_words = synonym.split()
    label_words = label.split()
    if len(syn_words) < 2 or len(label_words) > MAX_LABEL_WORDS:
        return 0.0
    padded = f" {label} "
    if "per" not in syn_words and any(f" {q} " in padded for q in _PER_QUALIFIERS):
        return 0.0
    n = len(syn_words)
    for i in range(len(label_words) - n + 1):
        if label_words[i : i + n] == syn_words:
            return 2.0 + 0.1 * n - 0.01 * (len(label_words) - n)
    return 0.0


def _best_score(label: str, synonyms: tuple[str, ...]) -> float:
    return max((label_score(label, s) for s in synonyms), default=0.0)


@dataclass(frozen=True)
class _Normalized:
    spec: FieldSpec
    synonyms: tuple[str, ...]


_FIELD_SYNONYMS = tuple(
    _Normalized(f, tuple(dict.fromkeys(normalize(s) for s in f.all_labels))) for f in FIELDS
)
_MIX_SYNONYMS = tuple(
    (c.key, tuple(dict.fromkeys(normalize(s) for s in (c.label, c.key, *c.synonyms))))
    for c in UNIT_MIX_COLUMNS
)


def _is_label(cell: Cell) -> bool:
    return (
        isinstance(cell.value, str)
        and parse_number(cell.value) is None
        and 0 < len(cell.value.strip()) <= MAX_LABEL_CHARS
    )


def _is_unit_marker(cell: Cell) -> bool:
    if not isinstance(cell.value, str):
        return False
    norm = normalize(cell.value)
    return not norm or set(norm.split()) <= _UNIT_WORDS


def percent_value(cell: Cell) -> tuple[Decimal | None, bool]:
    """The cell as a whole-number percent, and whether a bare fraction was
    scaled up (0.05 -> 5), which the review screen flags."""
    number = parse_number(cell.value)
    if number is None:
        return None, False
    if cell.percent_format:
        return number * 100, False
    if has_percent_sign(cell.value):
        return number, False
    if 0 < abs(number) < 1:
        return number * 100, True
    return number, False


def match_choice(spec: FieldSpec, text: str) -> Choice | None:
    norm = normalize(text)
    if not norm:
        return None
    for choice in spec.choices:
        names = {normalize(choice.value), normalize(choice.label), *map(normalize, choice.synonyms)}
        if norm in names:
            return choice
    best: tuple[float, Choice] | None = None
    for choice in spec.choices:
        for name in (choice.label, *choice.synonyms):
            n = normalize(name)
            if f" {n} " in f" {norm} " and (best is None or len(n) > best[0]):
                best = (len(n), choice)
    return best[1] if best else None


def _accepts(spec: FieldSpec, cell: Cell) -> bool:
    if spec.kind in ("text", "choice"):
        return isinstance(cell.value, str) and not _is_unit_marker(cell)
    return parse_number(cell.value) is not None


def _value_cell(sheet: Sheet, label: Cell, spec: FieldSpec | None) -> tuple[Cell | None, bool]:
    """The value for a label: the first filled cell to its right (skipping
    unit markers like "%" or "years"), else the cell directly below.
    With no spec, any value is taken (used for the candidate list)."""
    # Text sits right beside its label; looking further would pick up notes.
    lookahead = (
        TEXT_LOOKAHEAD if spec is not None and spec.kind in ("text", "choice") else VALUE_LOOKAHEAD
    )
    for col in range(label.col + 1, label.col + 1 + lookahead):
        cell = sheet.get(label.row, col)
        if cell is None:
            continue
        if spec is None:
            if _is_unit_marker(cell):
                continue
            return cell, False
        if _accepts(spec, cell):
            return cell, False
        if _is_unit_marker(cell):
            continue
        break
    if spec is not None and spec.kind not in ("text", "choice"):
        below = sheet.get(label.row + 1, label.col)
        if below is not None and _accepts(spec, below):
            return below, True
    return None, False


def _convert(spec: FieldSpec, cell: Cell, label_norm: str) -> tuple[str | None, str | None]:
    """The cell's value in the form's units, and a note for the reviewer."""
    if spec.kind == "text":
        return cell.text[:255], None
    if spec.kind == "choice":
        choice = match_choice(spec, cell.text)
        if choice is None:
            return None, f'"{cell.text}" isn\'t one of the options. Pick one.'
        return choice.value, None
    if spec.kind == "percent":
        number, scaled = percent_value(cell)
        if number is None:
            return None, None
        note = f"Read {cell.text} as {format_decimal(number)}%." if scaled else None
        return format_decimal(number), note

    number = parse_number(cell.value)
    if number is None:
        return None, None
    note = None
    if spec.key == "spread_bps":
        if cell.percent_format:
            number, note = number * 10000, f"Converted {cell.text} to basis points."
        elif has_percent_sign(cell.value) or 0 < number < 20:
            number, note = number * 100, f"Read {cell.text} as a percent; converted to bps."
    elif spec.key == "io_months" and set(label_norm.split()) & _YEAR_WORDS:
        number, note = number * 12, f"Converted {cell.text} years to months."
    if spec.kind == "integer" and number == number.to_integral_value():
        return str(int(number)), note
    return format_decimal(number), note


# ---- unit mix -------------------------------------------------------------


@dataclass
class _MixTable:
    sheet: Sheet
    header_row: int
    first_col: int
    last_col: int
    mapping: dict[str, int | None]  # attribute -> sheet column
    rows: list[int]
    score: tuple[int, int]


def _find_mix_table(sheet: Sheet) -> _MixTable | None:
    rows = sorted({r for r, _ in sheet.cells})
    best: _MixTable | None = None
    for header_row in rows:
        header = sorted(
            (c for (r, _), c in sheet.cells.items() if r == header_row), key=lambda c: c.col
        )
        if len(header) < 3 or not all(_is_label(c) for c in header):
            continue
        scored = []
        for cell in header:
            norm = normalize(cell.value)
            for key, synonyms in _MIX_SYNONYMS:
                score = _best_score(norm, synonyms)
                if score > 0:
                    scored.append((score, key, cell.col))
        mapping: dict[str, int | None] = {key: None for key, _ in _MIX_SYNONYMS}
        used: set[int] = set()
        for _score, key, col in sorted(scored, key=lambda s: -s[0]):
            if mapping[key] is None and col not in used:
                mapping[key] = col
                used.add(col)
        numeric = [k for k in ("units", "bedsPerUnit", "avgSqFt", "rent") if mapping[k]]
        if len(numeric) < 2:
            continue
        first_col, last_col = header[0].col, header[-1].col
        if mapping["name"] is None:
            leftmost = min(c for c in mapping.values() if c)
            mapping["name"] = header[0].col if header[0].col < leftmost else max(1, leftmost - 1)
            first_col = min(first_col, mapping["name"])

        data_rows: list[int] = []
        blanks = 0
        for row in range(header_row + 1, header_row + 1 + MAX_MIX_ROWS + 3):
            span = [sheet.get(row, c) for c in range(first_col, last_col + 1)]
            if not any(span):
                blanks += 1
                if data_rows or blanks > 1:
                    break
                continue
            name_cell = sheet.get(row, mapping["name"])
            if name_cell is not None and _SUMMARY_ROW.match(normalize(name_cell.text)):
                break
            if any(
                (cell := sheet.get(row, mapping[k])) is not None
                and parse_number(cell.value) is not None
                for k in numeric
            ):
                data_rows.append(row)
            if len(data_rows) >= MAX_MIX_ROWS:
                break
        if not data_rows:
            continue
        table = _MixTable(
            sheet,
            header_row,
            first_col,
            last_col,
            mapping,
            data_rows,
            (len(numeric) + (1 if mapping["name"] in used else 0), len(data_rows)),
        )
        if best is None or table.score > best.score:
            best = table
    return best


def _mix_out(table: _MixTable) -> UnitMixOut:
    cols = list(range(table.first_col, table.last_col + 1))
    columns = []
    for i, col in enumerate(cols):
        header = table.sheet.get(table.header_row, col)
        columns.append(
            MixColumnOut(
                index=i, letter=get_column_letter(col), header=header.text if header else ""
            )
        )
    rows = []
    for row in table.rows:
        cells = []
        for col in cols:
            cell = table.sheet.get(row, col)
            number = parse_number(cell.value) if cell else None
            cells.append(
                MixCellOut(
                    text=cell.text if cell else "",
                    number=None if number is None else format_decimal(number),
                )
            )
        rows.append(MixRowOut(row=row, cells=cells))
    mapping = {k: (None if c is None else cols.index(c)) for k, c in table.mapping.items()}
    return UnitMixOut(
        sheet=table.sheet.name,
        header_row=table.header_row,
        columns=columns,
        rows=rows,
        mapping=mapping,
    )


def _table_region(table: _MixTable | None) -> set[tuple[str, int, int]]:
    if table is None:
        return set()
    return {
        (table.sheet.name, row, col)
        for row in (table.header_row, *table.rows)
        for col in range(table.first_col, table.last_col + 1)
    }


# ---- fields ---------------------------------------------------------------


def _candidate(label: Cell, value: Cell) -> CandidateOut:
    number = parse_number(value.value)
    percent, _ = percent_value(value)
    return CandidateOut(
        id=value.address,
        sheet=value.sheet,
        cell=value.ref,
        label=label.text,
        text=value.text,
        number=None if number is None else format_decimal(number),
        percent=None if percent is None else format_decimal(percent),
    )


def build_proposal(filename: str, sheets: list[Sheet]) -> ImportProposal:
    scanned = [s for s in sheets if normalize(s.name) not in SKIPPED_SHEETS] or sheets

    tables = [t for t in (_find_mix_table(s) for s in scanned) if t is not None]
    table = max(tables, key=lambda t: t.score) if tables else None
    region = _table_region(table)

    labels: list[tuple[Sheet, Cell, str]] = []
    for sheet in scanned:
        for key in sorted(sheet.cells):
            cell = sheet.cells[key]
            if (sheet.name, cell.row, cell.col) in region or not _is_label(cell):
                continue
            labels.append((sheet, cell, normalize(cell.value)))

    candidates: dict[str, CandidateOut] = {}
    for sheet, label, _ in labels:
        if len(candidates) >= MAX_CANDIDATES:
            break
        value, _ = _value_cell(sheet, label, None)
        if value is not None and value.address not in candidates and not _is_label_only(value):
            candidates[value.address] = _candidate(label, value)

    matches = []
    for order, (sheet, label, norm) in enumerate(labels):
        for field in _FIELD_SYNONYMS:
            score = _best_score(norm, field.synonyms)
            if score <= 0:
                continue
            value, below = _value_cell(sheet, label, field.spec)
            if value is None:
                continue
            matches.append((score - (0.5 if below else 0.0), order, field.spec, label, norm, value))
    matches.sort(key=lambda m: (-m[0], m[1]))

    found: dict[str, FieldOut] = {}
    used: set[str] = set()
    for score, _, spec, label, norm, value in matches:
        if spec.key in found or label.address in used or value.address in used:
            continue
        converted, note = _convert(spec, value, norm)
        if converted is None and note is None:
            continue
        used.update((label.address, value.address))
        if value.address not in candidates:
            candidates[value.address] = _candidate(label, value)
        found[spec.key] = _field_out(
            spec,
            converted,
            SourceOut(sheet=value.sheet, cell=value.ref, label=label.text),
            value.address,
            "high" if score >= 3 and note is None else "medium",
            note,
        )

    fields = [
        found.get(spec.key) or _field_out(spec, None, None, None, None, None) for spec in FIELDS
    ]
    warnings = []
    if not found and table is None:
        warnings.append(
            "We couldn't recognize any deal inputs in this file. You can still point each "
            "field at a cell below, or download the template."
        )
    return ImportProposal(
        filename=filename,
        sheets=[s.name for s in sheets],
        fields=fields,
        candidates=list(candidates.values()),
        unit_mix=_mix_out(table) if table else None,
        warnings=warnings,
    )


def _is_label_only(cell: Cell) -> bool:
    # A long block of prose to the right of a label isn't a value.
    return isinstance(cell.value, str) and len(cell.value) > MAX_LABEL_CHARS


def _field_out(
    spec: FieldSpec,
    value: str | None,
    source: SourceOut | None,
    candidate_id: str | None,
    confidence: str | None,
    note: str | None,
) -> FieldOut:
    return FieldOut(
        key=spec.key,
        label=spec.label,
        section=spec.section,
        group=spec.group,
        kind=spec.kind,
        unit=spec.unit,
        choices=[ChoiceOut(value=c.value, label=c.label) for c in spec.choices],
        value=value,
        source=source,
        candidate_id=candidate_id,
        confidence=confidence,
        note=note,
    )

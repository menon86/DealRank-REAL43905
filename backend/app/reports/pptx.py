"""PPTX export. See docs/build-plan.md 6.3 — same content as the PDF, as
slides: title, comparison table, ranking, assumptions. This is the
artifact that gets presented, so it carries the methodology note about
unlevered-IRR ranking directly on the ranking slide, not just in an
appendix.
"""

import io
from decimal import Decimal

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from app.api.ranking_data import RANKING_BASIS_NOTE, RankedEntry
from app.reports.formatting import money, multiple, number, percent

_PRIMARY = RGBColor(0x1F, 0x4B, 0x99)
_MUTED = RGBColor(0x5B, 0x64, 0x74)
_HEADER_TEXT = RGBColor(0xFF, 0xFF, 0xFF)

_BLANK_LAYOUT_INDEX = 6  # "Blank" in the default python-pptx template


def _add_title_slide(prs: Presentation, hurdle_rate: Decimal, deal_count: int) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "DealRank — Deal Comparison & Ranking"
    subtitle = slide.placeholders[1]
    subtitle.text = f"Hurdle rate: {percent(hurdle_rate)}  |  {deal_count} deals compared"


def _new_content_slide(prs: Presentation, title: str):
    slide = prs.slides.add_slide(prs.slide_layouts[_BLANK_LAYOUT_INDEX])
    title_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.25), Inches(9.2), Inches(0.6))
    tf = title_box.text_frame
    tf.text = title
    tf.paragraphs[0].font.size = Pt(24)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = _PRIMARY
    return slide


def _style_table(table, header_row: bool = True) -> None:
    for row_idx, row in enumerate(table.rows):
        for cell in row.cells:
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.size = Pt(11 if row_idx == 0 else 10)
                if header_row and row_idx == 0:
                    paragraph.font.bold = True
                    paragraph.font.color.rgb = _HEADER_TEXT
            if header_row and row_idx == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = _PRIMARY


def _add_comparison_slide(prs: Presentation, entries: list[RankedEntry]) -> None:
    slide = _new_content_slide(prs, "Comparison")

    labels_and_values = [
        ("Hold period", lambda e: f"{e.deal.hold_period_years} yrs"),
        ("Year 1 NOI", lambda e: money(e.metrics.year_one_noi)),
        ("Going-in cap rate", lambda e: percent(e.metrics.going_in_cap_rate)),
        ("Year 1 DSCR", lambda e: number(e.metrics.year_one_dscr)),
        ("Cash-on-cash", lambda e: percent(e.metrics.cash_on_cash)),
        ("Unlevered IRR", lambda e: percent(e.metrics.unlevered_irr)),
        ("Levered IRR", lambda e: percent(e.metrics.levered_irr)),
        ("Equity multiple", lambda e: multiple(e.metrics.equity_multiple)),
    ]

    rows = 1 + len(labels_and_values)
    cols = 1 + len(entries)
    table_shape = slide.shapes.add_table(
        rows, cols, Inches(0.4), Inches(1.0), Inches(9.2), Inches(0.4) * rows
    )
    table = table_shape.table

    table.cell(0, 0).text = "Deal"
    for col, entry in enumerate(entries, start=1):
        table.cell(0, col).text = entry.deal.name

    for row, (label, extractor) in enumerate(labels_and_values, start=1):
        table.cell(row, 0).text = label
        for col, entry in enumerate(entries, start=1):
            table.cell(row, col).text = extractor(entry)

    _style_table(table)


def _add_ranking_slide(prs: Presentation, entries: list[RankedEntry]) -> None:
    slide = _new_content_slide(prs, "Ranking")

    rows = 1 + len(entries)
    table_shape = slide.shapes.add_table(
        rows, 5, Inches(0.4), Inches(1.0), Inches(9.2), Inches(0.4) * rows
    )
    table = table_shape.table

    headers = ["Rank", "Deal", "Unlevered IRR", "Levered IRR", "Spread vs. hurdle"]
    for col, header in enumerate(headers):
        table.cell(0, col).text = header

    for row, entry in enumerate(entries, start=1):
        spread_str = (
            "n/a (non-converging)"
            if entry.spread == Decimal("-Infinity")
            else f"{'+' if entry.spread >= 0 else ''}{percent(entry.spread)}"
        )
        table.cell(row, 0).text = f"#{entry.rank}"
        table.cell(row, 1).text = entry.deal.name
        table.cell(row, 2).text = percent(entry.metrics.unlevered_irr)
        table.cell(row, 3).text = percent(entry.metrics.levered_irr)
        table.cell(row, 4).text = spread_str

    _style_table(table)

    note_box = slide.shapes.add_textbox(
        Inches(0.4), Inches(1.0) + Inches(0.4) * rows + Inches(0.2), Inches(9.2), Inches(0.8)
    )
    tf = note_box.text_frame
    tf.word_wrap = True
    tf.text = RANKING_BASIS_NOTE
    tf.paragraphs[0].font.size = Pt(11)
    tf.paragraphs[0].font.color.rgb = _MUTED
    tf.paragraphs[0].font.italic = True


def _add_assumptions_slide(prs: Presentation, entry: RankedEntry) -> None:
    slide = _new_content_slide(prs, f"Assumptions — {entry.deal.name}")
    deal = entry.deal

    fields: list[tuple[str, str]] = [
        ("Sub-asset class", deal.sub_asset_class.value),
        ("Leasing mode", deal.leasing_mode.value),
        (
            "Units / beds",
            str(deal.unit_count) if deal.unit_count is not None else str(deal.bed_count),
        ),
        (
            "Monthly rent",
            (
                money(deal.monthly_rent_per_unit)
                if deal.monthly_rent_per_unit is not None
                else money(deal.monthly_rent_per_bed)
            ),
        ),
        ("Vacancy rate", percent(deal.vacancy_rate)),
        ("Other income, annual", money(deal.other_income_annual)),
        ("OpEx, annual", money(deal.opex_annual)),
        ("Expense growth rate", percent(deal.expense_growth_rate)),
        ("Rent growth rate", percent(deal.rent_growth_rate)),
        ("Turnover cost / unit or bed", money(deal.turnover_cost_per_unit_or_bed)),
        ("Annual turnover rate", percent(deal.annual_turnover_rate)),
        ("Purchase price", money(deal.purchase_price)),
        ("Closing costs", money(deal.closing_costs)),
        ("Loan amount", money(deal.loan_amount)),
        ("Interest rate", percent(deal.interest_rate)),
        ("Amortization (years)", str(deal.amortization_years)),
        ("Hold period (years)", str(deal.hold_period_years)),
        ("Exit cap rate", percent(deal.exit_cap_rate)),
        ("Selling costs rate", percent(deal.selling_costs_rate)),
    ]

    rows = len(fields)
    table_shape = slide.shapes.add_table(
        rows, 2, Inches(0.4), Inches(1.0), Inches(6.0), Inches(0.35) * rows
    )
    table = table_shape.table
    for row, (label, value) in enumerate(fields):
        table.cell(row, 0).text = label
        table.cell(row, 1).text = value
    _style_table(table, header_row=False)


def build_pptx_bytes(entries: list[RankedEntry], hurdle_rate: Decimal) -> bytes:
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    _add_title_slide(prs, hurdle_rate, len(entries))
    _add_comparison_slide(prs, entries)
    _add_ranking_slide(prs, entries)
    for entry in entries:
        _add_assumptions_slide(prs, entry)

    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue()

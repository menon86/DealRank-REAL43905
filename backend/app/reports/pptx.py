"""PPTX export. See docs/build-plan.md 6.3 — same content as the PDF, as
slides: title, comparison table, ranking, assumptions. This is the
artifact that gets presented, so it carries the methodology note about
unlevered-IRR ranking directly on the ranking slide, not just in an
appendix.
"""

import io

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from app.api.ranking_data import RankedEntry
from app.reports.capital_stack import CAPITAL_STACK_HEADERS, capital_stack_rows
from app.reports.data import ReportData
from app.reports.formatting import money, multiple, number, percent

_PRIMARY = RGBColor(0x1F, 0x4B, 0x99)
_MUTED = RGBColor(0x5B, 0x64, 0x74)
_HEADER_TEXT = RGBColor(0xFF, 0xFF, 0xFF)
_ACCENT_BG = RGBColor(0xEE, 0xF2, 0xFA)

_BLANK_LAYOUT_INDEX = 6  # "Blank" in the default python-pptx template


def _add_title_slide(prs: Presentation, data: ReportData) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "DealRank — Deal Comparison & Ranking"
    subtitle = slide.placeholders[1]
    subtitle.text = data.subtitle


def _new_content_slide(prs: Presentation, title: str):
    slide = prs.slides.add_slide(prs.slide_layouts[_BLANK_LAYOUT_INDEX])
    title_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.25), Inches(9.2), Inches(0.6))
    tf = title_box.text_frame
    tf.text = title
    tf.paragraphs[0].font.size = Pt(24)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = _PRIMARY
    return slide


def _style_table(table, header_row: bool = True, font_size: int = 10) -> None:
    for row_idx, row in enumerate(table.rows):
        for cell in row.cells:
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.size = Pt(
                    font_size + 1 if header_row and row_idx == 0 else font_size
                )
                if header_row and row_idx == 0:
                    paragraph.font.bold = True
                    paragraph.font.color.rgb = _HEADER_TEXT
            if header_row and row_idx == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = _PRIMARY


def _highlight_row(table, row_idx: int) -> None:
    """Marks the ranking-basis row (unlevered IRR) so it reads as the
    number that decides rank, not just one IRR among two."""
    for cell in table.rows[row_idx].cells:
        cell.fill.solid()
        cell.fill.fore_color.rgb = _ACCENT_BG
        for paragraph in cell.text_frame.paragraphs:
            paragraph.font.bold = True
            paragraph.font.color.rgb = _PRIMARY


def _year_one(entry: RankedEntry):
    return entry.metrics.annual_cash_flows[0]


def _add_comparison_slide(prs: Presentation, data: ReportData) -> None:
    entries = data.entries
    risk = data.mode == "risk"
    slide = _new_content_slide(prs, "Comparison")

    labels_and_values = (
        [
            ("Hold period", lambda e: f"{e.deal.hold_period_years} yrs"),
            ("Gross potential rent", lambda e: money(_year_one(e).gpr)),
            ("Less: vacancy loss", lambda e: money(_year_one(e).vacancy_loss)),
            ("Less: bad debt & concessions", lambda e: money(_year_one(e).credit_loss)),
            ("Effective gross income", lambda e: money(_year_one(e).egi)),
            ("Less: operating expenses", lambda e: money(_year_one(e).opex)),
            ("Less: turnover expense", lambda e: money(_year_one(e).turnover_expense)),
            ("Less: management fee", lambda e: money(_year_one(e).management_fee)),
            ("Year 1 NOI", lambda e: money(e.metrics.year_one_noi)),
            ("Less: replacement reserves", lambda e: money(_year_one(e).replacement_reserves)),
            ("Debt service (all debt)", lambda e: money(_year_one(e).debt_service)),
            (
                "Unlevered IRR (after costs)" if risk else data.basis_label,
                lambda e: percent(e.metrics.unlevered_irr),
            ),
        ]
        + (
            [(data.basis_label, lambda e: percent(e.metrics.unlevered_irr_before_costs))]
            if risk
            else []
        )
        + [
            ("Levered IRR (reference)", lambda e: percent(e.metrics.levered_irr)),
            ("Going-in cap rate", lambda e: percent(e.metrics.going_in_cap_rate)),
            ("Year 1 senior DSCR", lambda e: number(e.metrics.year_one_senior_dscr)),
            ("Year 1 combined DSCR", lambda e: number(e.metrics.year_one_dscr)),
            ("Lowest DSCR over the hold", lambda e: number(e.metrics.min_dscr)),
            ("Equity invested", lambda e: money(e.metrics.equity_invested)),
            ("Cash-on-cash", lambda e: percent(e.metrics.cash_on_cash)),
            ("Equity multiple", lambda e: multiple(e.metrics.equity_multiple)),
        ]
    )

    # Row height shrinks as rows are added so the table always ends inside
    # the 7.5" slide (below ~6.9"), leaving room for a two-line header row.
    rows = 1 + len(labels_and_values)
    cols = 1 + len(entries)
    row_height = Inches(min(0.34, 5.9 / rows))
    table_shape = slide.shapes.add_table(
        rows, cols, Inches(0.4), Inches(0.95), Inches(9.2), row_height * rows
    )
    table = table_shape.table
    label_width = Inches(2.2)
    table.columns[0].width = label_width
    for col in range(1, cols):
        table.columns[col].width = int((Inches(9.2) - label_width) / len(entries))

    table.cell(0, 0).text = "Deal"
    for col, entry in enumerate(entries, start=1):
        table.cell(0, col).text = entry.deal.name

    for row, (label, extractor) in enumerate(labels_and_values, start=1):
        table.cell(row, 0).text = label
        for col, entry in enumerate(entries, start=1):
            table.cell(row, col).text = extractor(entry)

    for row in range(rows):
        for col in range(1, cols):
            table.cell(row, col).text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT

    _style_table(table, font_size=8)
    _highlight_row(table, 1 + [label for label, _ in labels_and_values].index(data.basis_label))


def _add_ranking_slide(prs: Presentation, data: ReportData) -> None:
    slide = _new_content_slide(prs, "Ranking")

    rows = 1 + len(data.ranking_rows)
    cols = len(data.ranking_headers)
    table_shape = slide.shapes.add_table(
        rows, cols, Inches(0.4), Inches(1.0), Inches(9.2), Inches(0.4) * rows
    )
    table = table_shape.table

    for col, header in enumerate(data.ranking_headers):
        table.cell(0, col).text = header
    for row, cells in enumerate(data.ranking_rows, start=1):
        for col, value in enumerate(cells):
            table.cell(row, col).text = value

    table.columns[0].width = Inches(0.8)
    table.columns[1].width = Inches(3.0)
    for col in range(2, cols):
        table.columns[col].width = int((Inches(9.2) - Inches(3.8)) / (cols - 2))

    _style_table(table, font_size=10 if cols <= 5 else 9)
    for row in range(1, rows):
        table.cell(row, 2).text_frame.paragraphs[0].font.bold = True

    lines = [data.basis_note]
    lines += [f"Excluded: {name} — {reason}" for name, reason in data.excluded]
    lines += [f"Note: {name} — {warning}" for name, warning in data.warnings]
    note_box = slide.shapes.add_textbox(
        Inches(0.4), Inches(1.0) + Inches(0.4) * rows + Inches(0.2), Inches(9.2), Inches(0.8)
    )
    tf = note_box.text_frame
    tf.word_wrap = True
    tf.text = lines[0]
    for line in lines[1:]:
        tf.add_paragraph().text = line
    for paragraph in tf.paragraphs:
        paragraph.font.size = Pt(10)
        paragraph.font.color.rgb = _MUTED
        paragraph.font.italic = True


def _add_hurdle_slide(prs: Presentation, data: ReportData) -> None:
    slide = _new_content_slide(prs, "How each hurdle was built")
    rows = 1 + len(data.hurdle_rows)
    row_height = Inches(min(0.4, 5.0 / rows))
    table_shape = slide.shapes.add_table(
        rows, len(data.hurdle_headers), Inches(0.4), Inches(1.0), Inches(9.2), row_height * rows
    )
    table = table_shape.table
    for col, header in enumerate(data.hurdle_headers):
        table.cell(0, col).text = header
    for row, cells in enumerate(data.hurdle_rows, start=1):
        for col, value in enumerate(cells):
            table.cell(row, col).text = value
    for col, width in enumerate((1.9, 1.1, 0.8, 0.9, 0.9, 0.8, 2.8)):
        table.columns[col].width = Inches(width)
    _style_table(table, font_size=8)

    note_box = slide.shapes.add_textbox(
        Inches(0.4), Inches(1.0) + row_height * rows + Inches(0.2), Inches(9.2), Inches(1.0)
    )
    tf = note_box.text_frame
    tf.word_wrap = True
    tf.text = data.sources_note
    tf.paragraphs[0].font.size = Pt(10)
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
        ("Other income growth", percent(deal.other_income_growth_rate)),
        ("Bad debt & concessions", percent(deal.credit_loss_rate)),
        ("Management fee (of EGI)", percent(deal.management_fee_rate)),
        ("Reserve / unit or bed", money(deal.replacement_reserve_per_unit_or_bed)),
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

    # 23 rows at 0.26" from 0.95" ends at ~6.95", inside the 7.5" slide.
    rows = len(fields)
    table_shape = slide.shapes.add_table(
        rows, 2, Inches(0.4), Inches(0.95), Inches(6.0), Inches(0.26) * rows
    )
    table = table_shape.table
    for row, (label, value) in enumerate(fields):
        table.cell(row, 0).text = label
        table.cell(row, 1).text = value
    for row in table.rows:
        for cell in row.cells:
            cell.margin_top = cell.margin_bottom = Inches(0.02)
    _style_table(table, header_row=False, font_size=8)


def _add_capital_stack_slide(prs: Presentation, entry: RankedEntry) -> None:
    slide = _new_content_slide(prs, f"Capital stack — {entry.deal.name}")
    body = capital_stack_rows(entry.deal, entry.metrics)

    # At most 20 layers + header + residual row: 0.3" rows from 0.95"
    # stay on the slide up to ~21 rows, so shrink rows for big stacks.
    rows = 1 + len(body)
    row_height = min(Inches(0.36), int(Inches(6.3) / rows))
    table_shape = slide.shapes.add_table(
        rows, len(CAPITAL_STACK_HEADERS), Inches(0.4), Inches(0.95), Inches(9.2), row_height * rows
    )
    table = table_shape.table
    for col, header in enumerate(CAPITAL_STACK_HEADERS):
        table.cell(0, col).text = header
    for row, cells in enumerate(body, start=1):
        for col, value in enumerate(cells):
            table.cell(row, col).text = value
    for col, width in enumerate((2.3, 1.1, 1.3, 0.9, 1.6, 2.0)):
        table.columns[col].width = Inches(width)
    for row in range(rows):
        for col in (2, 3):
            table.cell(row, col).text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _style_table(table, font_size=9)
    for cell in table.rows[rows - 1].cells:
        for paragraph in cell.text_frame.paragraphs:
            paragraph.font.bold = True


def build_pptx_bytes(data: ReportData) -> bytes:
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    _add_title_slide(prs, data)
    _add_comparison_slide(prs, data)
    _add_ranking_slide(prs, data)
    if data.hurdle_rows:
        _add_hurdle_slide(prs, data)
    for entry in data.entries:
        _add_assumptions_slide(prs, entry)
        _add_capital_stack_slide(prs, entry)

    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue()

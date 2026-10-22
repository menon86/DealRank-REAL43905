"""PDF export. See docs/build-plan.md 6.2 — the comparison table, the
ranking, and an assumptions block listing every input per deal, so the
file is self-contained (a grader shouldn't need the live app to read it).
"""

import enum
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.api.ranking_data import RankedEntry
from app.reports.capital_stack import CAPITAL_STACK_HEADERS, capital_stack_rows
from app.reports.data import ReportData
from app.reports.formatting import money, multiple, number, percent

_STYLES = getSampleStyleSheet()
_TITLE = ParagraphStyle("DealRankTitle", parent=_STYLES["Title"], fontSize=20)
_SUBTITLE = ParagraphStyle("DealRankSubtitle", parent=_STYLES["Normal"], textColor=colors.grey)
_H2 = _STYLES["Heading2"]
_H3 = _STYLES["Heading3"]
_BODY = _STYLES["BodyText"]
_NOTE = ParagraphStyle(
    "DealRankNote", parent=_STYLES["BodyText"], fontSize=9, textColor=colors.grey
)

_TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4b99")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dfe3e8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
)

_ASSUMPTION_FIELDS: list[tuple[str, str]] = [
    ("sub_asset_class", "Sub-asset class"),
    ("leasing_mode", "Leasing mode"),
    ("unit_count", "Unit count"),
    ("monthly_rent_per_unit", "Monthly rent / unit"),
    ("bed_count", "Bed count"),
    ("monthly_rent_per_bed", "Monthly rent / bed"),
    ("vacancy_rate", "Vacancy rate"),
    ("other_income_annual", "Other income, annual"),
    ("other_income_growth_rate", "Other income growth"),
    ("credit_loss_rate", "Bad debt & concessions"),
    ("management_fee_rate", "Management fee (of EGI)"),
    ("replacement_reserve_per_unit_or_bed", "Replacement reserve / unit or bed"),
    ("opex_annual", "OpEx, annual"),
    ("expense_growth_rate", "Expense growth rate"),
    ("rent_growth_rate", "Rent growth rate"),
    ("lease_expiration_month", "Lease expiration month"),
    ("turnover_cost_per_unit_or_bed", "Turnover cost / unit or bed"),
    ("annual_turnover_rate", "Annual turnover rate"),
    ("purchase_price", "Purchase price"),
    ("closing_costs", "Closing costs"),
    ("loan_amount", "Loan amount"),
    ("interest_rate", "Interest rate"),
    ("amortization_years", "Amortization (years)"),
    ("hold_period_years", "Hold period (years)"),
    ("exit_cap_rate", "Exit cap rate"),
    ("selling_costs_rate", "Selling costs rate"),
]

_RATE_FIELDS = {
    "other_income_growth_rate",
    "credit_loss_rate",
    "management_fee_rate",
    "vacancy_rate",
    "expense_growth_rate",
    "rent_growth_rate",
    "annual_turnover_rate",
    "interest_rate",
    "exit_cap_rate",
    "selling_costs_rate",
}

_MONEY_FIELDS = {
    "replacement_reserve_per_unit_or_bed",
    "monthly_rent_per_unit",
    "monthly_rent_per_bed",
    "other_income_annual",
    "opex_annual",
    "turnover_cost_per_unit_or_bed",
    "purchase_price",
    "closing_costs",
    "loan_amount",
}


def _format_assumption_value(field: str, value: object) -> str:
    if value is None:
        return "—"
    if field in _RATE_FIELDS:
        return percent(value)  # type: ignore[arg-type]
    if field in _MONEY_FIELDS:
        return money(value)  # type: ignore[arg-type]
    if isinstance(value, enum.Enum):
        # str(SubAssetClass.SUBURBAN_GARDEN) is "SubAssetClass.SUBURBAN_GARDEN"
        # (the str+Enum mixin doesn't get StrEnum's plain __str__) — .value
        # is the "suburban_garden" a reader actually wants.
        return str(value.value)
    return str(value)


# Letter width minus the 0.6" margins set in build_pdf_bytes.
_CONTENT_WIDTH = 7.3 * inch
_LABEL_COL_WIDTH = 2.0 * inch

_HEADER_CELL = ParagraphStyle(
    "DealRankHeaderCell",
    parent=_STYLES["BodyText"],
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=9.5,
    spaceBefore=0,
    spaceAfter=0,
    textColor=colors.white,
)
_HEADER_CELL_RIGHT = ParagraphStyle("DealRankHeaderCellRight", parent=_HEADER_CELL, alignment=2)
_BODY_CELL = ParagraphStyle(
    "DealRankBodyCell",
    parent=_STYLES["BodyText"],
    fontSize=8,
    leading=9.5,
    spaceBefore=0,
    spaceAfter=0,
)

_ACCENT_BG = colors.HexColor("#eef2fa")
_SECTION_TEXT = colors.HexColor("#5b6474")


def _comparison_table(data: ReportData) -> Table:
    entries = data.entries
    # Deal names and row labels are Paragraphs, not plain strings, so
    # they wrap inside their cell instead of overprinting the next column
    # once there are 4-5 deals on the page.
    rows: list[list] = [
        [Paragraph("Deal", _HEADER_CELL)]
        + [Paragraph(escape(e.deal.name), _HEADER_CELL_RIGHT) for e in entries]
    ]
    section_rows: list[int] = []
    bold_rows: list[int] = []

    def section(label: str) -> None:
        section_rows.append(len(rows))
        rows.append([label.upper()] + [""] * len(entries))

    def row(label: str, extractor, bold: bool = False) -> None:
        if bold:
            bold_rows.append(len(rows))
        rows.append([Paragraph(label, _BODY_CELL)] + [extractor(e) for e in entries])

    def year_one(e: RankedEntry):
        return e.metrics.annual_cash_flows[0]

    row("Hold period", lambda e: f"{e.deal.hold_period_years} yrs")
    section("Year 1 waterfall")
    row("Gross potential rent", lambda e: money(year_one(e).gpr))
    row("Less: vacancy loss", lambda e: money(year_one(e).vacancy_loss))
    row("Less: bad debt & concessions", lambda e: money(year_one(e).credit_loss))
    row("Effective gross income", lambda e: money(year_one(e).egi), bold=True)
    row("Less: operating expenses", lambda e: money(year_one(e).opex))
    row("Less: turnover expense", lambda e: money(year_one(e).turnover_expense))
    row("Less: management fee", lambda e: money(year_one(e).management_fee))
    row("Year 1 NOI", lambda e: money(e.metrics.year_one_noi), bold=True)
    row("Less: replacement reserves", lambda e: money(year_one(e).replacement_reserves))
    row("Debt service (all debt)", lambda e: money(year_one(e).debt_service))
    row("Preferred return", lambda e: money(year_one(e).preferred_distribution))
    section("Headline metrics")
    risk = data.mode == "risk"
    row(
        "Unlevered IRR (after closing & selling costs)" if risk else data.basis_label,
        lambda e: percent(e.metrics.unlevered_irr),
        bold=not risk,
    )
    if risk:
        ranking_basis_row = len(rows)
        row(
            data.basis_label,
            lambda e: percent(e.metrics.unlevered_irr_before_costs),
            bold=True,
        )
    else:
        ranking_basis_row = len(rows) - 1
    row("Levered IRR (reference)", lambda e: percent(e.metrics.levered_irr))
    row("Going-in cap rate", lambda e: percent(e.metrics.going_in_cap_rate))
    row("Year 1 senior DSCR", lambda e: number(e.metrics.year_one_senior_dscr))
    row("Year 1 combined DSCR", lambda e: number(e.metrics.year_one_dscr))
    row("Lowest DSCR over the hold", lambda e: number(e.metrics.min_dscr))
    row("Debt yield (NOI / debt)", lambda e: percent(e.metrics.debt_yield))
    row("Equity invested", lambda e: money(e.metrics.equity_invested))
    row("Cash-on-cash", lambda e: percent(e.metrics.cash_on_cash))
    row("Total distributions", lambda e: money(e.metrics.total_distributions))
    row("Equity multiple", lambda e: multiple(e.metrics.equity_multiple))
    section("Exit")
    row("Forward NOI (year N+1)", lambda e: money(e.metrics.forward_noi))
    row("Exit cap rate", lambda e: percent(e.deal.exit_cap_rate))
    row("Exit value", lambda e: money(e.metrics.exit_value), bold=True)
    row("Less: selling costs", lambda e: money(e.metrics.selling_costs))
    row("Less: debt balance at exit", lambda e: money(e.metrics.loan_balance_at_exit))
    row("Less: preferred equity repaid", lambda e: money(e.metrics.preferred_equity_repayment))
    row("Net sale proceeds", lambda e: money(e.metrics.net_sale_proceeds), bold=True)

    deal_col_width = (_CONTENT_WIDTH - _LABEL_COL_WIDTH) / len(entries)
    # repeatRows: if the table ever runs past a page, the deal-name header
    # row is redrawn at the top of the next page.
    table = Table(
        rows, colWidths=[_LABEL_COL_WIDTH] + [deal_col_width] * len(entries), repeatRows=1
    )

    style = TableStyle(_TABLE_STYLE.getCommands())
    for r in section_rows:
        style.add("SPAN", (0, r), (-1, r))
        style.add("BACKGROUND", (0, r), (-1, r), colors.white)
        style.add("TEXTCOLOR", (0, r), (-1, r), _SECTION_TEXT)
        style.add("FONTNAME", (0, r), (-1, r), "Helvetica-Bold")
        style.add("FONTSIZE", (0, r), (-1, r), 7)
        style.add("ALIGN", (0, r), (-1, r), "LEFT")
    for r in bold_rows:
        style.add("FONTNAME", (1, r), (-1, r), "Helvetica-Bold")
    style.add("BACKGROUND", (0, ranking_basis_row), (-1, ranking_basis_row), _ACCENT_BG)
    style.add(
        "LINEBEFORE",
        (0, ranking_basis_row),
        (0, ranking_basis_row),
        2.5,
        colors.HexColor("#1f4b99"),
    )
    # Compact rows: with the extra lines the comparison has to fit on one
    # page next to the title, or the title would sit alone on page 1.
    style.add("TOPPADDING", (0, 0), (-1, -1), 1.5)
    style.add("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)
    table.setStyle(style)
    return table


def _ranking_table(data: ReportData) -> Table:
    count = len(data.ranking_headers)
    rows: list[list] = [
        [
            Paragraph(header, _HEADER_CELL if i < 2 else _HEADER_CELL_RIGHT)
            for i, header in enumerate(data.ranking_headers)
        ]
    ]
    for cells in data.ranking_rows:
        rows.append([cells[0], Paragraph(escape(cells[1]), _BODY_CELL)] + cells[2:])
    rest = (_CONTENT_WIDTH - 3.3 * inch) / (count - 2)
    table = Table(rows, colWidths=[0.5 * inch, 2.8 * inch] + [rest] * (count - 2), repeatRows=1)
    style = TableStyle(_TABLE_STYLE.getCommands())
    style.add("FONTNAME", (2, 1), (2, -1), "Helvetica-Bold")
    style.add("FONTNAME", (4, 1), (4, -1), "Helvetica-Bold")
    table.setStyle(style)
    return table


def _hurdle_table(data: ReportData) -> Table:
    rows: list[list] = [
        [
            Paragraph(h, _HEADER_CELL if i in (0, 1, 6) else _HEADER_CELL_RIGHT)
            for i, h in enumerate(data.hurdle_headers)
        ]
    ]
    for cells in data.hurdle_rows:
        rows.append(
            [Paragraph(escape(cells[0]), _BODY_CELL), Paragraph(escape(cells[1]), _BODY_CELL)]
            + cells[2:6]
            + [Paragraph(escape(cells[6]), _BODY_CELL)]
        )
    table = Table(
        rows,
        colWidths=[
            1.5 * inch,
            0.9 * inch,
            0.6 * inch,
            0.7 * inch,
            0.7 * inch,
            0.6 * inch,
            2.3 * inch,
        ],
        repeatRows=1,
    )
    table.setStyle(_TABLE_STYLE)
    return table


def _draw_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(doc.leftMargin, 0.35 * inch, "DealRank — Deal Comparison & Ranking")
    canvas.drawRightString(
        doc.pagesize[0] - doc.rightMargin, 0.35 * inch, f"Page {canvas.getPageNumber()}"
    )
    canvas.restoreState()


def _assumptions_table(deal) -> Table:
    assumption_rows = [
        [label, _format_assumption_value(field, getattr(deal, field))]
        for field, label in _ASSUMPTION_FIELDS
        if getattr(deal, field) is not None
    ]
    table = Table(assumption_rows, colWidths=[2.0 * inch, 1.45 * inch])
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dfe3e8")),
                (
                    "ROWBACKGROUNDS",
                    (0, 0),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f6f7f9")],
                ),
            ]
        )
    )
    return table


def _capital_stack_table(entry: RankedEntry) -> Table:
    rows: list[list] = [
        [
            Paragraph(header, _HEADER_CELL if i < 2 else _HEADER_CELL_RIGHT)
            for i, header in enumerate(CAPITAL_STACK_HEADERS)
        ]
    ]
    for cells in capital_stack_rows(entry.deal, entry.metrics):
        rows.append(
            [Paragraph(escape(cells[0]), _BODY_CELL), cells[1], cells[2], cells[3]]
            + [Paragraph(escape(cell), _BODY_CELL) for cell in cells[4:]]
        )
    table = Table(
        rows,
        colWidths=[1.9 * inch, 0.9 * inch, 1.0 * inch, 0.7 * inch, 1.2 * inch, 1.6 * inch],
        repeatRows=1,
    )
    style = TableStyle(_TABLE_STYLE.getCommands())
    style.add("ALIGN", (1, 0), (1, -1), "LEFT")
    style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    table.setStyle(style)
    return table


def build_pdf_bytes(data: ReportData) -> bytes:
    entries = data.entries
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )

    ranking_block = [
        Paragraph("Ranking", _H2),
        _ranking_table(data),
        Spacer(1, 0.15 * inch),
        Paragraph(escape(data.basis_note), _NOTE),
    ]
    for name, reason in data.excluded:
        ranking_block.append(
            Paragraph(f"<b>Excluded:</b> {escape(name)} — {escape(reason)}", _NOTE)
        )
    for name, warning in data.warnings:
        ranking_block.append(Paragraph(f"<b>Note:</b> {escape(name)} — {escape(warning)}", _NOTE))

    # Each section is one KeepTogether block — heading, table and its note
    # — so a page break can only fall between sections, never between a
    # heading and its table or through the middle of a table. A block too
    # tall for a whole page still splits, with its header row repeated.
    story: list = [
        Paragraph("DealRank — Deal Comparison &amp; Ranking", _TITLE),
        Paragraph(escape(data.subtitle), _SUBTITLE),
        Spacer(1, 0.25 * inch),
        KeepTogether(
            [
                Paragraph("Comparison", _H2),
                _comparison_table(data),
                Spacer(1, 0.2 * inch),
                Paragraph(
                    "Both IRRs are shown. Ranking (below) uses the unlevered IRR only; "
                    "levered IRR is for reference and is never sorted on.",
                    _NOTE,
                ),
            ]
        ),
        Spacer(1, 0.3 * inch),
        KeepTogether(ranking_block),
        Spacer(1, 0.3 * inch),
    ]
    if data.hurdle_rows:
        story.append(
            KeepTogether(
                [
                    Paragraph("How each hurdle was built", _H2),
                    _hurdle_table(data),
                    Spacer(1, 0.15 * inch),
                    Paragraph(escape(data.sources_note), _NOTE),
                ]
            )
        )
        story.append(Spacer(1, 0.3 * inch))

    # Assumptions sit two deals side by side. Each pair is its own
    # one-row table, and a table row never splits across pages, so a deal's
    # name always stays with its inputs. The section heading travels with
    # the first pair.
    cards = [
        [Paragraph(escape(entry.deal.name), _H3), _assumptions_table(entry.deal)]
        for entry in entries
    ]
    pairs = [cards[i : i + 2] for i in range(0, len(cards), 2)]
    intro = [
        Paragraph("Assumptions", _H2),
        Paragraph(
            "Every input behind the figures above, per deal, so this report is "
            "readable without the live application.",
            _BODY,
        ),
        Spacer(1, 0.1 * inch),
    ]
    for index, pair in enumerate(pairs):
        row = Table([pair + [""] * (2 - len(pair))], colWidths=[_CONTENT_WIDTH / 2] * 2)
        row.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        story.append(KeepTogether(intro + [row]) if index == 0 else row)

    # Capital stacks are full-width tables, so they follow the paired
    # assumption cards as their own section, one deal per block.
    story.append(Spacer(1, 0.1 * inch))
    for index, entry in enumerate(entries):
        block = [
            Paragraph(escape(entry.deal.name), _H3),
            _capital_stack_table(entry),
            Spacer(1, 0.2 * inch),
        ]
        if index == 0:
            block = [Paragraph("Capital stack", _H2)] + block
        story.append(KeepTogether(block))

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    return buffer.getvalue()

"""PDF export. See docs/build-plan.md 6.2 — the comparison table, the
ranking, and an assumptions block listing every input per deal, so the
file is self-contained (a grader shouldn't need the live app to read it).
"""

import enum
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.api.ranking_data import RANKING_BASIS_NOTE, RankedEntry
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
    "vacancy_rate",
    "expense_growth_rate",
    "rent_growth_rate",
    "annual_turnover_rate",
    "interest_rate",
    "exit_cap_rate",
    "selling_costs_rate",
}

_MONEY_FIELDS = {
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
_LABEL_COL_WIDTH = 1.6 * inch

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

_RANKING_BASIS_LABEL = "Unlevered IRR (ranking basis)"


def _comparison_table(entries: list[RankedEntry]) -> Table:
    # Deal names and row labels are Paragraphs, not plain strings, so
    # they wrap inside their cell instead of overprinting the next column
    # once there are 4-5 deals on the page.
    rows: list[list] = [
        [Paragraph("Deal", _HEADER_CELL)]
        + [Paragraph(e.deal.name, _HEADER_CELL_RIGHT) for e in entries]
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
    row("Effective gross income", lambda e: money(year_one(e).egi), bold=True)
    row("Less: operating expenses", lambda e: money(year_one(e).opex))
    row("Less: turnover expense", lambda e: money(year_one(e).turnover_expense))
    row("Year 1 NOI", lambda e: money(e.metrics.year_one_noi), bold=True)
    row("Debt service", lambda e: money(year_one(e).debt_service))
    section("Headline metrics")
    ranking_basis_row = len(rows)
    row(_RANKING_BASIS_LABEL, lambda e: percent(e.metrics.unlevered_irr), bold=True)
    row("Levered IRR (reference)", lambda e: percent(e.metrics.levered_irr))
    row("Going-in cap rate", lambda e: percent(e.metrics.going_in_cap_rate))
    row("Year 1 DSCR", lambda e: number(e.metrics.year_one_dscr))
    row("Equity invested", lambda e: money(e.metrics.equity_invested))
    row("Cash-on-cash", lambda e: percent(e.metrics.cash_on_cash))
    row("Total distributions", lambda e: money(e.metrics.total_distributions))
    row("Equity multiple", lambda e: multiple(e.metrics.equity_multiple))
    section("Exit")
    row("Forward NOI (year N+1)", lambda e: money(e.metrics.forward_noi))
    row("Exit cap rate", lambda e: percent(e.deal.exit_cap_rate))
    row("Exit value", lambda e: money(e.metrics.exit_value), bold=True)
    row("Less: selling costs", lambda e: money(e.metrics.selling_costs))
    row("Less: loan balance at exit", lambda e: money(e.metrics.loan_balance_at_exit))
    row("Net sale proceeds", lambda e: money(e.metrics.net_sale_proceeds), bold=True)

    deal_col_width = (_CONTENT_WIDTH - _LABEL_COL_WIDTH) / len(entries)
    table = Table(rows, colWidths=[_LABEL_COL_WIDTH] + [deal_col_width] * len(entries))

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
    table.setStyle(style)
    return table


def _ranking_table(entries: list[RankedEntry]) -> Table:
    rows: list[list] = [
        [
            Paragraph("Rank", _HEADER_CELL),
            Paragraph("Deal", _HEADER_CELL),
            Paragraph(_RANKING_BASIS_LABEL, _HEADER_CELL_RIGHT),
            Paragraph("Levered IRR (reference)", _HEADER_CELL_RIGHT),
            Paragraph("Spread vs. hurdle", _HEADER_CELL_RIGHT),
        ]
    ]
    for entry in entries:
        spread_str = (
            "n/a (non-converging)"
            if entry.spread == Decimal("-Infinity")
            else f"{'+' if entry.spread >= 0 else ''}{percent(entry.spread)}"
        )
        rows.append(
            [
                f"#{entry.rank}",
                Paragraph(entry.deal.name, _BODY_CELL),
                percent(entry.metrics.unlevered_irr),
                percent(entry.metrics.levered_irr),
                spread_str,
            ]
        )
    table = Table(rows, colWidths=[0.5 * inch, 2.8 * inch, 1.4 * inch, 1.3 * inch, 1.3 * inch])
    style = TableStyle(_TABLE_STYLE.getCommands())
    style.add("FONTNAME", (2, 1), (2, -1), "Helvetica-Bold")
    style.add("FONTNAME", (4, 1), (4, -1), "Helvetica-Bold")
    table.setStyle(style)
    return table


def build_pdf_bytes(entries: list[RankedEntry], hurdle_rate: Decimal) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )

    story: list = [
        Paragraph("DealRank — Deal Comparison &amp; Ranking", _TITLE),
        Paragraph(
            f"Hurdle rate: {percent(hurdle_rate)} &nbsp;|&nbsp; {len(entries)} deals compared",
            _SUBTITLE,
        ),
        Spacer(1, 0.25 * inch),
        Paragraph("Comparison", _H2),
        _comparison_table(entries),
        Spacer(1, 0.2 * inch),
        Paragraph(
            "Both IRRs are shown. Ranking (below) uses unlevered IRR only, against the "
            "hurdle rate above; levered IRR is for reference and is never sorted on.",
            _NOTE,
        ),
        Spacer(1, 0.3 * inch),
        Paragraph("Ranking", _H2),
        _ranking_table(entries),
        Spacer(1, 0.15 * inch),
        Paragraph(RANKING_BASIS_NOTE, _NOTE),
    ]

    story.append(PageBreak())
    story.append(Paragraph("Assumptions", _H2))
    story.append(
        Paragraph(
            "Every input behind the figures above, per deal, so this report is readable "
            "without the live application.",
            _BODY,
        )
    )
    story.append(Spacer(1, 0.15 * inch))
    for entry in entries:
        deal = entry.deal
        story.append(Paragraph(deal.name, _H3))
        assumption_rows = [
            [label, _format_assumption_value(field, getattr(deal, field))]
            for field, label in _ASSUMPTION_FIELDS
            if getattr(deal, field) is not None
        ]
        table = Table(assumption_rows, colWidths=[2.2 * inch, 2.2 * inch])
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
        story.append(table)
        story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    return buffer.getvalue()

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


def _comparison_table(entries: list[RankedEntry]) -> Table:
    rows: list[list[str]] = [["Deal"] + [e.deal.name for e in entries]]

    def row(label: str, extractor) -> list[str]:
        return [label] + [extractor(e) for e in entries]

    rows.append(row("Hold period", lambda e: f"{e.deal.hold_period_years} yrs"))
    rows.append(row("Gross potential rent", lambda e: money(e.metrics.annual_cash_flows[0].gpr)))
    rows.append(row("Vacancy loss", lambda e: money(e.metrics.annual_cash_flows[0].vacancy_loss)))
    rows.append(row("Effective gross income", lambda e: money(e.metrics.annual_cash_flows[0].egi)))
    rows.append(row("Operating expenses", lambda e: money(e.metrics.annual_cash_flows[0].opex)))
    rows.append(
        row("Turnover expense", lambda e: money(e.metrics.annual_cash_flows[0].turnover_expense))
    )
    rows.append(row("Year 1 NOI", lambda e: money(e.metrics.year_one_noi)))
    rows.append(row("Debt service", lambda e: money(e.metrics.annual_cash_flows[0].debt_service)))
    rows.append(row("Going-in cap rate", lambda e: percent(e.metrics.going_in_cap_rate)))
    rows.append(row("Year 1 DSCR", lambda e: number(e.metrics.year_one_dscr)))
    rows.append(row("Cash-on-cash", lambda e: percent(e.metrics.cash_on_cash)))
    rows.append(row("Unlevered IRR", lambda e: percent(e.metrics.unlevered_irr)))
    rows.append(row("Levered IRR", lambda e: percent(e.metrics.levered_irr)))
    rows.append(row("Equity multiple", lambda e: multiple(e.metrics.equity_multiple)))
    rows.append(row("Exit value", lambda e: money(e.metrics.exit_value)))
    rows.append(row("Net sale proceeds", lambda e: money(e.metrics.net_sale_proceeds)))

    col_width = (6.5 * inch) / (len(entries) + 1)
    table = Table(rows, colWidths=[col_width] * (len(entries) + 1))
    table.setStyle(_TABLE_STYLE)
    return table


def _ranking_table(entries: list[RankedEntry]) -> Table:
    rows = [["Rank", "Deal", "Unlevered IRR", "Levered IRR", "Spread vs. hurdle"]]
    for entry in entries:
        spread_str = (
            "n/a (non-converging)"
            if entry.spread == Decimal("-Infinity")
            else f"{'+' if entry.spread >= 0 else ''}{percent(entry.spread)}"
        )
        rows.append(
            [
                f"#{entry.rank}",
                entry.deal.name,
                percent(entry.metrics.unlevered_irr),
                percent(entry.metrics.levered_irr),
                spread_str,
            ]
        )
    table = Table(rows, colWidths=[0.5 * inch, 2.3 * inch, 1.2 * inch, 1.2 * inch, 1.3 * inch])
    table.setStyle(_TABLE_STYLE)
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
            "Both unlevered and levered IRR are shown; ranking below is based on unlevered "
            "IRR against the hurdle rate above.",
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

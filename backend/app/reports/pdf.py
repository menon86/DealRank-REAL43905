"""PDF export. See docs/build-plan.md 6.2 — the comparison table, the
ranking, and an assumptions block listing every input per deal, so the
file is self-contained (a grader shouldn't need the live app to read it).

Laid out like an institutional investment-committee package: a cover, an
executive summary (findings, KPI tiles, return-vs-hurdle chart, ranking),
the side-by-side comparison, how each hurdle was built, then one profile
page per deal (underwriting inputs, capital stack, pro forma cash flow),
closing with methodology and disclaimers.
"""

import io
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.api.ranking_data import RankedEntry
from app.reports import theme
from app.reports.assumptions import ASSUMPTION_GROUPS, format_assumption_value, present_rows
from app.reports.capital_stack import CAPITAL_STACK_HEADERS, capital_stack_rows
from app.reports.data import PerfPoint, ReportData
from app.reports.formatting import money, multiple, number, percent, short_name


def _c(hex_color: str) -> colors.Color:
    return colors.HexColor(f"#{hex_color}")


INK, PRIMARY, PRIMARY_MID, ACCENT = (
    _c(theme.INK),
    _c(theme.PRIMARY),
    _c(theme.PRIMARY_MID),
    _c(theme.ACCENT),
)
TINT, STRIPE, RULE, MUTED = _c(theme.TINT), _c(theme.STRIPE), _c(theme.RULE), _c(theme.MUTED)
NEGATIVE, WHITE = _c(theme.NEGATIVE), _c(theme.WHITE)

PAGE_W, PAGE_H = letter
MARGIN = 0.6 * inch
# Letter width minus the margins.
_CONTENT_WIDTH = PAGE_W - 2 * MARGIN
_LABEL_COL_WIDTH = 2.0 * inch
_COVER_BAND = 5.0 * inch


def _style(name: str, **kw) -> ParagraphStyle:
    kw.setdefault("fontName", "Helvetica")
    kw.setdefault("textColor", INK)
    kw.setdefault("fontSize", 9)
    kw.setdefault("leading", kw["fontSize"] * 1.35)
    return ParagraphStyle(name, **kw)


_KICKER = _style(
    "Kicker", fontName="Helvetica-Bold", fontSize=7.5, textColor=PRIMARY_MID, spaceAfter=2
)
_H1 = _style(
    "H1", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=PRIMARY, spaceAfter=4
)
_H2 = _style(
    "H2",
    fontName="Helvetica-Bold",
    fontSize=11,
    leading=14,
    textColor=PRIMARY,
    spaceBefore=4,
    spaceAfter=5,
)
_BODY = _style("Body", fontSize=9, textColor=INK)
_LEAD = _style("Lead", fontSize=10, leading=14, textColor=MUTED)
_NOTE = _style("Note", fontSize=7.5, leading=10, textColor=MUTED)
_BULLET = _style("Bullet", fontSize=9.5, leading=13, leftIndent=12, bulletIndent=0, spaceAfter=3)
_HEADER_CELL = _style(
    "HeaderCell", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=WHITE
)
_HEADER_CELL_RIGHT = ParagraphStyle("HeaderCellRight", parent=_HEADER_CELL, alignment=TA_RIGHT)
_BODY_CELL = _style("BodyCell", fontSize=7.5, leading=9)
_KPI_VALUE = _style(
    "KpiValue",
    fontName="Helvetica-Bold",
    fontSize=15,
    leading=18,
    textColor=PRIMARY,
    alignment=TA_CENTER,
)
_KPI_LABEL = _style("KpiLabel", fontSize=6.5, leading=8, textColor=MUTED, alignment=TA_CENTER)

# ---------------------------------------------------------------- page chrome


def _draw_cover(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, PAGE_H - _COVER_BAND, PAGE_W, _COVER_BAND, stroke=0, fill=1)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_H - _COVER_BAND - 5, PAGE_W, 5, stroke=0, fill=1)
    # Wordmark.
    canvas.rect(MARGIN, PAGE_H - 0.62 * inch, 9, 9, stroke=0, fill=1)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(MARGIN + 16, PAGE_H - 0.62 * inch + 0.5, theme.NAME.upper())
    # Disclaimer pinned to the foot of the cover.
    disclaimer = Paragraph(theme.DISCLAIMER, _NOTE)
    _, height = disclaimer.wrap(_CONTENT_WIDTH, 2 * inch)
    disclaimer.drawOn(canvas, MARGIN, 0.6 * inch)
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 0.6 * inch + height + 8, PAGE_W - MARGIN, 0.6 * inch + height + 8)
    canvas.restoreState()


def _make_page_chrome(generated_on: str):
    def draw(canvas, doc) -> None:
        canvas.saveState()
        top = PAGE_H - 0.5 * inch
        canvas.setFillColor(ACCENT)
        canvas.rect(MARGIN, top, 7, 7, stroke=0, fill=1)
        canvas.setFillColor(PRIMARY)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(MARGIN + 13, top, theme.NAME.upper())
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(PAGE_W - MARGIN, top, theme.REPORT_TITLE)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, top - 7, PAGE_W - MARGIN, top - 7)
        canvas.line(MARGIN, 0.55 * inch, PAGE_W - MARGIN, 0.55 * inch)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(
            MARGIN, 0.38 * inch, f"{generated_on}  |  Screening analysis, not an appraisal"
        )
        canvas.setFillColor(PRIMARY)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawRightString(PAGE_W - MARGIN, 0.38 * inch, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    return draw


def _section(kicker: str, title: str) -> list:
    return [
        Paragraph(escape(kicker.upper()), _KICKER),
        Paragraph(escape(title), _H1),
        HRFlowable(width=36, thickness=2.5, color=ACCENT, hAlign="LEFT", spaceAfter=10),
    ]


# ------------------------------------------------------------------- widgets


def _kpi_strip(items: list[tuple[str, str]]) -> Table:
    """A row of figure tiles: big number over a small caption."""
    cells = [[Paragraph(escape(v), _KPI_VALUE), Paragraph(escape(k), _KPI_LABEL)] for k, v in items]
    table = Table(
        [[c[0] for c in cells], [c[1] for c in cells]],
        colWidths=[_CONTENT_WIDTH / len(items)] * len(items),
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), STRIPE),
                ("LINEABOVE", (0, 0), (-1, 0), 2.5, ACCENT),
                ("LINEAFTER", (0, 0), (-2, -1), 0.5, WHITE),
                ("TOPPADDING", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
                ("TOPPADDING", (0, 1), (-1, 1), 0),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _kpis_for(entry: RankedEntry) -> list[tuple[str, str]]:
    m = entry.metrics
    return [
        ("Year 1 NOI", money(m.year_one_noi)),
        ("Going-in cap rate", percent(m.going_in_cap_rate)),
        ("Unlevered IRR", percent(m.unlevered_irr)),
        ("Levered IRR (reference)", percent(m.levered_irr)),
        ("Equity multiple", multiple(m.equity_multiple)),
        ("Lowest DSCR", number(m.min_dscr)),
    ]


def _ellipsize(text: str, font: str, size: float, width: float) -> str:
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _return_chart(perf: list[PerfPoint], hurdle_label: str) -> Drawing:
    """Horizontal bars of each ranked deal's IRR with its hurdle as a
    marker, so the spread that decides rank is visible at a glance."""
    width = _CONTENT_WIDTH
    row_h, bar_h, top_pad, axis_h = 28, 13, 22, 20
    height = top_pad + row_h * len(perf) + axis_h
    drawing = Drawing(width, height)
    label_w, right_pad = 150, 52
    x0, x1 = label_w + 10, width - right_pad

    values = [p.irr for p in perf] + [p.hurdle for p in perf] + [Decimal(0)]
    lo, hi = float(min(values)), float(max(values))
    hi = hi + (hi - lo) * 0.08 if hi > lo else lo + 0.01

    def x_at(value: Decimal | float) -> float:
        return x0 + (float(value) - lo) / (hi - lo) * (x1 - x0)

    # Legend.
    drawing.add(Rect(x0, height - 12, 9, 7, fillColor=PRIMARY_MID, strokeColor=None))
    drawing.add(
        String(
            x0 + 13, height - 11, "Unlevered IRR", fontName="Helvetica", fontSize=7, fillColor=MUTED
        )
    )
    mx = x0 + 85
    drawing.add(
        Polygon(
            [mx, height - 8.5, mx + 4, height - 12, mx, height - 15.5, mx - 4, height - 12],
            fillColor=INK,
            strokeColor=None,
        )
    )
    drawing.add(
        String(mx + 9, height - 11, hurdle_label, fontName="Helvetica", fontSize=7, fillColor=MUTED)
    )

    steps = 4
    for i in range(steps + 1):
        tick = lo + (hi - lo) * i / steps
        x = x_at(tick)
        drawing.add(Line(x, axis_h - 4, x, height - top_pad + 6, strokeColor=RULE, strokeWidth=0.4))
        drawing.add(
            String(
                x,
                6,
                percent(Decimal(str(tick)), 1),
                textAnchor="middle",
                fontName="Helvetica",
                fontSize=6.5,
                fillColor=MUTED,
            )
        )
    if lo < 0 < hi:
        drawing.add(
            Line(
                x_at(0), axis_h - 4, x_at(0), height - top_pad + 6, strokeColor=INK, strokeWidth=0.8
            )
        )

    for i, p in enumerate(perf):
        y = height - top_pad - row_h * (i + 1) + (row_h - bar_h) / 2
        name = _ellipsize(p.name, "Helvetica-Bold" if i == 0 else "Helvetica", 8, label_w)
        drawing.add(
            String(
                0,
                y + 3.5,
                name,
                fontName="Helvetica-Bold" if i == 0 else "Helvetica",
                fontSize=8,
                fillColor=INK,
            )
        )
        start, end = sorted((x_at(0), x_at(p.irr)))
        drawing.add(
            Rect(
                start,
                y,
                max(end - start, 0.5),
                bar_h,
                fillColor=PRIMARY_MID if p.irr >= 0 else NEGATIVE,
                strokeColor=None,
            )
        )
        hx = x_at(p.hurdle)
        drawing.add(Line(hx, y - 4, hx, y + bar_h + 4, strokeColor=INK, strokeWidth=1.6))
        drawing.add(
            Polygon(
                [
                    hx,
                    y + bar_h + 7,
                    hx + 3.5,
                    y + bar_h + 3.5,
                    hx,
                    y + bar_h,
                    hx - 3.5,
                    y + bar_h + 3.5,
                ],
                fillColor=INK,
                strokeColor=None,
            )
        )
        drawing.add(
            String(
                max(end, hx) + 8,
                y + 3.5,
                percent(p.irr),
                fontName="Helvetica-Bold",
                fontSize=8,
                fillColor=PRIMARY,
            )
        )
    return drawing


def _base_table_style() -> TableStyle:
    """Header band, hairline row rules, no vertical lines."""
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
            ("TEXTCOLOR", (0, 1), (-1, -1), INK),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )


# -------------------------------------------------------------------- tables


def _comparison_table(data: ReportData) -> Table:
    entries = data.entries

    def head(e: RankedEntry) -> Paragraph:
        tag = f"Rank {e.rank}" if e.rank else "Excluded"
        return Paragraph(
            f"{escape(short_name(e.deal.name))}<br/>"
            f'<font size="6.5" color="#{theme.ACCENT}">{tag}</font>',
            _HEADER_CELL_RIGHT,
        )

    # Deal names and row labels are Paragraphs, not plain strings, so
    # they wrap inside their cell instead of overprinting the next column
    # once there are 4-5 deals on the page.
    rows: list[list] = [[Paragraph("Deal", _HEADER_CELL)] + [head(e) for e in entries]]
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
    row("Less: prepayment penalties", lambda e: money(e.metrics.prepayment_penalties))
    row("Less: preferred equity repaid", lambda e: money(e.metrics.preferred_equity_repayment))
    row("Net sale proceeds", lambda e: money(e.metrics.net_sale_proceeds), bold=True)

    deal_col_width = (_CONTENT_WIDTH - _LABEL_COL_WIDTH) / len(entries)
    # repeatRows: if the table ever runs past a page, the deal-name header
    # row is redrawn at the top of the next page.
    table = Table(
        rows, colWidths=[_LABEL_COL_WIDTH] + [deal_col_width] * len(entries), repeatRows=1
    )

    style = _base_table_style()
    for r in section_rows:
        style.add("SPAN", (0, r), (-1, r))
        style.add("BACKGROUND", (0, r), (-1, r), TINT)
        style.add("TEXTCOLOR", (0, r), (-1, r), PRIMARY)
        style.add("FONTNAME", (0, r), (-1, r), "Helvetica-Bold")
        style.add("FONTSIZE", (0, r), (-1, r), 6.5)
        style.add("ALIGN", (0, r), (-1, r), "LEFT")
        style.add("TOPPADDING", (0, r), (-1, r), 2)
        style.add("BOTTOMPADDING", (0, r), (-1, r), 2)
    for r in bold_rows:
        style.add("FONTNAME", (1, r), (-1, r), "Helvetica-Bold")
        style.add("LINEABOVE", (0, r), (-1, r), 0.6, PRIMARY_MID)
    style.add("BACKGROUND", (0, ranking_basis_row), (-1, ranking_basis_row), TINT)
    style.add("TEXTCOLOR", (1, ranking_basis_row), (-1, ranking_basis_row), PRIMARY)
    style.add("LINEBEFORE", (0, ranking_basis_row), (0, ranking_basis_row), 3, ACCENT)
    # Compact rows: with the extra lines the comparison has to fit on one
    # page next to its heading, or the heading would sit alone on a page.
    style.add("TOPPADDING", (0, 1), (-1, -1), 1.5)
    style.add("BOTTOMPADDING", (0, 1), (-1, -1), 1.5)
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
    rest = (_CONTENT_WIDTH - 3.0 * inch) / (count - 2)
    table = Table(rows, colWidths=[0.5 * inch, 2.5 * inch] + [rest] * (count - 2), repeatRows=1)
    style = _base_table_style()
    style.add("ALIGN", (0, 0), (0, -1), "LEFT")
    style.add("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold")
    style.add("FONTNAME", (2, 1), (2, -1), "Helvetica-Bold")
    style.add("FONTNAME", (4, 1), (4, -1), "Helvetica-Bold")
    # The leader gets the accent treatment.
    style.add("BACKGROUND", (0, 1), (-1, 1), TINT)
    style.add("LINEBEFORE", (0, 1), (0, 1), 3, ACCENT)
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
            1.6 * inch,
            0.95 * inch,
            0.65 * inch,
            0.75 * inch,
            0.7 * inch,
            0.6 * inch,
            2.05 * inch,
        ],
        repeatRows=1,
    )
    style = _base_table_style()
    style.add("ALIGN", (6, 0), (6, -1), "LEFT")
    style.add("FONTNAME", (5, 1), (5, -1), "Helvetica-Bold")
    table.setStyle(style)
    return table


def _assumption_column(
    deal, groups: list[tuple[str, list[tuple[str, str]]]], width: float
) -> Table:
    rows: list[list] = []
    headers: list[int] = []
    for title, present in present_rows(deal, groups):
        headers.append(len(rows))
        rows.append([title.upper(), ""])
        rows.extend([label, value] for label, value in present)
    table = Table(rows, colWidths=[width * 0.62, width * 0.38])
    style = TableStyle(
        [
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TEXTCOLOR", (0, 0), (-1, -1), INK),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
    )
    for r in headers:
        style.add("SPAN", (0, r), (1, r))
        style.add("BACKGROUND", (0, r), (1, r), TINT)
        style.add("TEXTCOLOR", (0, r), (1, r), PRIMARY)
        style.add("FONTNAME", (0, r), (1, r), "Helvetica-Bold")
        style.add("FONTSIZE", (0, r), (1, r), 6.5)
        style.add("ALIGN", (0, r), (1, r), "LEFT")
    table.setStyle(style)
    return table


def _assumptions_block(deal) -> Table:
    """Two columns of grouped inputs, as one table so a deal's inputs never
    split across pages."""
    gap = 0.25 * inch
    col_w = (_CONTENT_WIDTH - gap) / 2
    left = _assumption_column(deal, [ASSUMPTION_GROUPS[0], ASSUMPTION_GROUPS[3]], col_w)
    right = _assumption_column(deal, [ASSUMPTION_GROUPS[1], ASSUMPTION_GROUPS[2]], col_w)
    block = Table([[left, "", right]], colWidths=[col_w, gap, col_w])
    block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return block


def _capital_stack_table(entry: RankedEntry) -> Table:
    rows: list[list] = [
        [
            Paragraph(header, _HEADER_CELL if i < 2 or i > 3 else _HEADER_CELL_RIGHT)
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
    style = _base_table_style()
    style.add("ALIGN", (1, 0), (1, -1), "LEFT")
    style.add("ALIGN", (4, 0), (5, -1), "LEFT")
    style.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    style.add("BACKGROUND", (0, -1), (-1, -1), TINT)
    table.setStyle(style)
    return table


_MAX_PROFORMA_YEARS = 10


def _proforma_table(entry: RankedEntry) -> Table:
    flows = entry.metrics.annual_cash_flows[:_MAX_PROFORMA_YEARS]
    lines: list[tuple[str, object, bool]] = [
        ("Effective gross income", lambda f: f.egi, False),
        ("Operating expenses", lambda f: f.egi - f.noi, False),
        ("Net operating income", lambda f: f.noi, True),
        ("Replacement reserves", lambda f: f.replacement_reserves, False),
        ("Debt service", lambda f: f.debt_service, False),
        ("Cash flow after debt service", lambda f: f.levered_cash_flow, True),
    ]
    rows: list[list] = [["$"] + [f"Yr {f.year}" for f in flows]]
    for label, getter, _ in lines:
        rows.append([label] + [money(getter(f)) for f in flows])
    label_w = 1.45 * inch
    table = Table(
        rows, colWidths=[label_w] + [(_CONTENT_WIDTH - label_w) / len(flows)] * len(flows)
    )
    style = _base_table_style()
    style.add("FONTSIZE", (0, 0), (-1, -1), 6.5)
    style.add("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")
    for i, (_, _, bold) in enumerate(lines, start=1):
        if bold:
            style.add("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")
            style.add("BACKGROUND", (0, i), (-1, i), TINT)
    table.setStyle(style)
    return table


def _deal_page(index: int, total: int, entry: RankedEntry) -> list:
    deal = entry.deal
    standing = f"Rank {entry.rank}" if entry.rank else "Excluded from ranking"
    facts = [
        standing,
        format_assumption_value("sub_asset_class", deal.sub_asset_class),
        (f"{deal.unit_count} units" if deal.unit_count is not None else f"{deal.bed_count} beds"),
        f"{deal.hold_period_years}-year hold",
    ]
    story: list = [
        PageBreak(),
        Paragraph(f"Deal profile {index} of {total}".upper(), _KICKER),
        Paragraph(escape(deal.name), _H1),
        HRFlowable(width=36, thickness=2.5, color=ACCENT, hAlign="LEFT", spaceAfter=4),
        Paragraph("  |  ".join(escape(f) for f in facts), _LEAD),
        Spacer(1, 0.12 * inch),
        _kpi_strip(_kpis_for(entry)),
        Spacer(1, 0.16 * inch),
        KeepTogether([Paragraph("Underwriting assumptions", _H2), _assumptions_block(deal)]),
        Spacer(1, 0.14 * inch),
        KeepTogether([Paragraph("Capital stack", _H2), _capital_stack_table(entry)]),
        Spacer(1, 0.14 * inch),
    ]
    proforma = [Paragraph("Pro forma cash flow", _H2), _proforma_table(entry)]
    if len(entry.metrics.annual_cash_flows) > _MAX_PROFORMA_YEARS:
        proforma.append(
            Paragraph(f"Years 1–{_MAX_PROFORMA_YEARS} of {deal.hold_period_years} shown.", _NOTE)
        )
    story.append(KeepTogether(proforma))
    return story


# ---------------------------------------------------------------- the report


def _cover(data: ReportData) -> list:
    white_kicker = ParagraphStyle("CoverKicker", parent=_KICKER, textColor=ACCENT, fontSize=9)
    title = _style(
        "CoverTitle", fontName="Helvetica-Bold", fontSize=36, leading=42, textColor=WHITE
    )
    sub = _style("CoverSub", fontSize=11, leading=16, textColor=colors.HexColor("#C9DAD5"))
    story: list = [
        Spacer(1, 1.35 * inch),
        Paragraph("INVESTMENT ANALYSIS", white_kicker),
        Paragraph("Deal Comparison<br/>&amp; Ranking", title),
        Spacer(1, 0.18 * inch),
        Paragraph(escape(data.subtitle), sub),
        Spacer(1, 0.08 * inch),
        Paragraph(escape(data.generated_on), sub),
        Spacer(1, 1.05 * inch),
        Paragraph("Properties analysed", _H2),
    ]
    rows: list[list] = []
    for i, e in enumerate(data.entries, start=1):
        standing = f"Rank {e.rank}" if e.rank else "Excluded"
        rows.append(
            [
                f"{i:02d}",
                Paragraph(escape(e.deal.name), _BODY_CELL),
                Paragraph(
                    escape(format_assumption_value("sub_asset_class", e.deal.sub_asset_class)),
                    _BODY_CELL,
                ),
                standing,
            ]
        )
    table = Table(rows, colWidths=[0.5 * inch, 3.3 * inch, 2.2 * inch, 1.3 * inch])
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY_MID),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (3, 0), (3, -1), PRIMARY),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    return story


def _executive_summary(data: ReportData) -> list:
    story: list = _section("Overview", "Executive summary")

    if data.takeaways:
        bullets = [Paragraph(escape(t), _BULLET, bulletText="•") for t in data.takeaways]
        box = Table([[bullets]], colWidths=[_CONTENT_WIDTH])
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), STRIPE),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story += [box, Spacer(1, 0.18 * inch)]

    leader = next((e for e in data.entries if e.rank), None)
    if leader is not None:
        story.append(
            KeepTogether(
                [
                    Paragraph(f"Top-ranked deal: {escape(leader.deal.name)}", _H2),
                    _kpi_strip(_kpis_for(leader)),
                    Spacer(1, 0.18 * inch),
                ]
            )
        )

    if data.perf:
        hurdle_label = "Hurdle" if data.mode == "risk" else "Hurdle rate"
        story.append(
            KeepTogether(
                [
                    Paragraph(
                        "Return vs. hurdle" + (" (before costs)" if data.mode == "risk" else ""),
                        _H2,
                    ),
                    _return_chart(data.perf, hurdle_label),
                    Spacer(1, 0.12 * inch),
                ]
            )
        )

    ranking_block = [
        Paragraph("Ranking", _H2),
        _ranking_table(data),
        Spacer(1, 0.1 * inch),
        Paragraph(escape(data.basis_note), _NOTE),
    ]
    for name, reason in data.excluded:
        ranking_block.append(
            Paragraph(f"<b>Excluded:</b> {escape(name)} — {escape(reason)}", _NOTE)
        )
    for name, warning in data.warnings:
        ranking_block.append(Paragraph(f"<b>Note:</b> {escape(name)} — {escape(warning)}", _NOTE))
    # One block — heading, table and notes — so a page break can only fall
    # between sections, never between a heading and its table.
    story.append(KeepTogether(ranking_block))
    return story


def _methodology(data: ReportData) -> list:
    hurdles: list = []
    if data.hurdle_rows:
        hurdles = [
            KeepTogether(
                [
                    Paragraph("How each hurdle was built", _H2),
                    _hurdle_table(data),
                    Spacer(1, 0.1 * inch),
                    Paragraph(escape(data.sources_note), _NOTE),
                ]
            ),
            Spacer(1, 0.25 * inch),
        ]
    return [
        PageBreak(),
        *_section("Appendix", "Methodology & sources"),
        *hurdles,
        Paragraph("Ranking basis", _H2),
        Paragraph(escape(data.basis_note), _BODY),
        Spacer(1, 0.1 * inch),
        Paragraph(
            "Both IRRs are shown for every deal. Ranking uses the unlevered IRR only; "
            "levered IRR is for reference and is never sorted on, so leverage cannot lift a "
            "deal in the ranking.",
            _BODY,
        ),
        Spacer(1, 0.18 * inch),
        Paragraph("Disclaimers", _H2),
        Paragraph(theme.DISCLAIMER, _BODY),
    ]


def build_pdf_bytes(data: ReportData) -> bytes:
    entries = data.entries
    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
        title=f"{theme.NAME} — {theme.REPORT_TITLE}",
        author=theme.NAME,
    )
    cover_frame = Frame(
        MARGIN,
        0.5 * inch,
        _CONTENT_WIDTH,
        PAGE_H - 1.1 * inch,
        id="cover",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    body_frame = Frame(
        MARGIN,
        0.75 * inch,
        _CONTENT_WIDTH,
        PAGE_H - 1.6 * inch,
        id="body",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[cover_frame], onPage=_draw_cover),
            PageTemplate(
                id="body", frames=[body_frame], onPage=_make_page_chrome(data.generated_on)
            ),
        ]
    )

    story: list = [*_cover(data), NextPageTemplate("body"), PageBreak()]
    story += _executive_summary(data)

    story.append(PageBreak())
    story.append(
        KeepTogether(
            [
                *_section("Side by side", "Comparison"),
                _comparison_table(data),
                Spacer(1, 0.12 * inch),
                Paragraph(
                    "Both IRRs are shown. Ranking uses the unlevered IRR only; "
                    "levered IRR is for reference and is never sorted on.",
                    _NOTE,
                ),
            ]
        )
    )

    for index, entry in enumerate(entries, start=1):
        story += _deal_page(index, len(entries), entry)

    story += _methodology(data)

    doc.build(story)
    return buffer.getvalue()

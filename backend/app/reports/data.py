"""What the PDF and PPTX exports render. Both formats are built from one
ReportData so they cannot disagree, and the risk-adjusted report is built
from the same computation as POST /rank/risk-adjusted
(app/api/risk_rank.py compute_risk_ranking).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.api.ranking_data import RANKING_BASIS_NOTE, RankedEntry
from app.api.risk_rank import BASIS_NOTE as RISK_BASIS_NOTE
from app.api.risk_rank import RiskRanking
from app.reports.formatting import number, percent

# Label of the comparison-table row that decides rank.
FLAT_BASIS_LABEL = "Unlevered IRR (ranking basis)"
RISK_BASIS_LABEL = "Unlevered IRR before costs (ranking basis)"


@dataclass(frozen=True)
class ReportData:
    mode: str  # "flat" | "risk"
    # Every compared deal: ranked ones in rank order, then excluded ones.
    entries: list[RankedEntry]
    subtitle: str
    ranking_headers: list[str]
    ranking_rows: list[list[str]]
    basis_note: str
    basis_label: str
    # (deal name, reason) for deals the gates removed from the ranking.
    excluded: list[tuple[str, str]] = field(default_factory=list)
    # (deal name, warning) for assumptions that flatter the return.
    warnings: list[tuple[str, str]] = field(default_factory=list)
    # Header + rows describing how each deal's hurdle was built and where it came from.
    hurdle_headers: list[str] = field(default_factory=list)
    hurdle_rows: list[list[str]] = field(default_factory=list)
    sources_note: str = ""


SOURCES_NOTE = (
    "Hurdle = 10-year Treasury (live from FRED / Treasury.gov, or a fallback or "
    "user-entered value when labelled) + broker-survey cap-rate spread + assumed stabilized "
    "NOI growth. Survey figures are published CBRE, Berkadia and Yardi Matrix numbers "
    "transcribed by hand; deal inputs are the user's own assumptions. See the source memo "
    "for the full list and dates."
)


def flat_report(entries: list[RankedEntry], hurdle_rate: Decimal) -> ReportData:
    rows = []
    for entry in entries:
        spread = (
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
                spread,
            ]
        )
    return ReportData(
        mode="flat",
        entries=entries,
        subtitle=f"Hurdle rate: {percent(hurdle_rate)}  |  {len(entries)} deals compared",
        ranking_headers=[
            "Rank",
            "Deal",
            FLAT_BASIS_LABEL,
            "Levered IRR (reference)",
            "Spread vs. hurdle",
        ],
        ranking_rows=rows,
        basis_note=RANKING_BASIS_NOTE,
        basis_label=FLAT_BASIS_LABEL,
    )


def risk_report(result: RiskRanking) -> ReportData:
    entries: list[RankedEntry] = []
    rows: list[list[str]] = []
    scored = result.weights.irr != 1 or result.weights.cash_flow != 0 or result.weights.risk != 0
    for r in result.ranked:
        entries.append(RankedEntry(deal=r.deal, metrics=r.metrics, spread=r.spread, rank=r.rank))
        rows.append(
            [
                f"#{r.rank}",
                r.deal.name,
                percent(r.metrics.unlevered_irr_before_costs),
                percent(r.hurdle.total),
                f"{'+' if r.spread >= 0 else ''}{percent(r.spread)}",
                f"{number(r.metrics.min_dscr)}x" if r.metrics.min_dscr is not None else "—",
                percent(r.ltv, 1),
            ]
            + ([f"{r.score * 100:.0f}"] if scored else [])
        )
    for e in result.excluded:
        entries.append(
            RankedEntry(deal=e.deal, metrics=e.metrics, spread=Decimal("-Infinity"), rank=0)
        )

    headers = [
        "Rank",
        "Deal",
        "IRR before costs",
        "Hurdle",
        "Spread",
        "Lowest DSCR",
        "Debt / price",
    ] + (["Score (0–100)"] if scored else [])

    gates = f"DSCR minimum {number(result.dscr_minimum)}x"
    if result.debt_yield_minimum is not None:
        gates += f", debt-yield minimum {percent(result.debt_yield_minimum)}"
    treasury = result.treasury
    when = f" as of {treasury.as_of}" if treasury.as_of else ""
    subtitle = (
        f"{len(entries)} deals compared  |  10-year Treasury {percent(treasury.yield_)} "
        f"({treasury.source}{when})  |  {gates}"
    )

    hurdle_rows = [
        [
            r.deal.name,
            r.hurdle.sub_asset_class.replace("_", " "),
            percent(r.hurdle.treasury_yield),
            f"{r.hurdle.spread_bps} bps",
            percent(r.hurdle.noi_growth),
            percent(r.hurdle.total),
            f"{r.hurdle.survey_source} ({r.hurdle.survey_quarter})",
        ]
        for r in [*result.ranked, *result.excluded]
    ]
    return ReportData(
        mode="risk",
        entries=entries,
        subtitle=subtitle,
        ranking_headers=headers,
        ranking_rows=rows,
        basis_note=RISK_BASIS_NOTE,
        basis_label=RISK_BASIS_LABEL,
        excluded=[(e.deal.name, e.reason) for e in result.excluded],
        warnings=[(r.deal.name, w) for r in result.ranked for w in r.warnings],
        hurdle_headers=[
            "Deal",
            "Class",
            "Treasury",
            "Cap spread",
            "NOI growth",
            "Hurdle",
            "Survey",
        ],
        hurdle_rows=hurdle_rows,
        sources_note=SOURCES_NOTE,
    )

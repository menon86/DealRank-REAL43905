"""Deterministic answers to a fixed set of questions, with no LLM involved.

This is the chat's fallback when the model is rate-limited, down or not
configured. Each answer is templated text filled from the same tool functions
the assistant uses, so a preset and a model answer can't disagree on a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.api.chat_tools import (
    DealArg,
    NoArgs,
    RiskRankArgs,
    ToolContext,
    ToolError,
    get_hurdles,
    get_metrics,
    list_deals,
    risk_rank,
)


@dataclass(frozen=True)
class Preset:
    id: str
    question: str


PRESETS: tuple[Preset, ...] = (
    Preset("top_deal", "Why is the #1 deal ranked first?"),
    Preset("dscr_gate", "Which deals failed the DSCR gate and why?"),
    Preset("hurdle_breakdown", "Show the hurdle breakdown"),
    Preset("dscr_extremes", "Which deal has the highest and lowest DSCR?"),
    Preset("ranking_basis", "What is the ranking based on?"),
)
PRESET_BY_ID = {p.id: p for p in PRESETS}

DISCLAIMER = "Figures come from the DealRank engine. This is analysis, not investment advice."


def _treasury_line(t: dict[str, Any]) -> str:
    line = f"10-Year Treasury {t['yield']} ({t['source']}"
    line += f", as of {t['as_of']})" if t["as_of"] else ")"
    return line


def _ranking(ctx: ToolContext) -> dict[str, Any]:
    return risk_rank(ctx, RiskRankArgs())


def _top_deal(ctx: ToolContext) -> str:
    res = _ranking(ctx)
    if not res["ranked"]:
        return (
            "No deal is ranked: every deal was excluded by the DSCR gate. "
            "Ask 'Which deals failed the DSCR gate and why?' for details."
        )
    top = res["ranked"][0]
    h = top["hurdle"]
    lines = [
        f"{top['deal']} is ranked #1 of {len(res['ranked'])} ranked deal(s).",
        f"- Unlevered IRR (before costs): {top['unlevered_irr_before_costs']} vs its "
        f"{h['sub_asset_class']} hurdle of {h['total']} = spread {top['spread_vs_hurdle']}.",
        f"- Hurdle: Treasury {h['treasury']} + cap-rate spread {h['cap_rate_spread']} + "
        f"NOI growth {h['noi_growth']}.",
        f"- Lowest DSCR over the hold: {top['min_dscr']}; LTV {top['ltv']}.",
        f"- Weights: IRR {res['weights']['irr']}, cash flow {res['weights']['cash_flow']}, "
        f"risk {res['weights']['risk']}; score {top['score']}.",
        _treasury_line(res["treasury"]) + ".",
    ]
    for w in top["warnings"]:
        lines.append(f"- Caution: {w}")
    if len(res["ranked"]) > 1:
        nxt = res["ranked"][1]
        lines.append(
            f"- Next: {nxt['deal']} (score {nxt['score']}, spread {nxt['spread_vs_hurdle']})."
        )
    lines.append(res["basis_note"])
    return "\n".join(lines)


def _dscr_gate(ctx: ToolContext) -> str:
    res = _ranking(ctx)
    if not res["excluded"]:
        return (
            f"No deal was excluded. All {len(res['ranked'])} deal(s) cleared the "
            f"{res['dscr_minimum']} minimum DSCR (lowest DSCR over the hold)."
        )
    lines = [f"Excluded from ranking (minimum DSCR {res['dscr_minimum']}):"]
    lines += [f"- {e['deal']}: {e['reason']}" for e in res["excluded"]]
    lines.append("Excluded deals are removed from the ranking, not penalized within it.")
    return "\n".join(lines)


def _hurdle_breakdown(ctx: ToolContext) -> str:
    res = get_hurdles(ctx, NoArgs())
    lines = [f"{res['formula']}.", _treasury_line(res["treasury"]) + "."]
    if res["treasury"]["is_fallback"]:
        lines.append("Note: the Treasury figure is a fallback default, not a live quote.")
    for h in res["hurdles"]:
        lines.append(
            f"- {h['sub_asset_class']}: {h['treasury']} + {h['cap_rate_spread']} "
            f"(= cap rate {h['cap_rate']}) + {h['noi_growth']} NOI growth = "
            f"{h['total_hurdle']} ({h['survey']})."
        )
    return "\n".join(lines)


def _dscr_extremes(ctx: ToolContext) -> str:
    deals = list_deals(ctx, NoArgs())["deals"]
    rows = []
    for d in deals:
        m = get_metrics(ctx, DealArg(deal=d["id"]))
        raw = m["min_dscr_over_hold"]
        if raw is not None:
            rows.append((Decimal(raw.removesuffix("x")), d["name"], m))
    if not rows:
        return "No deal has a DSCR to compare (all-cash deals have no debt service)."
    rows.sort(key=lambda r: r[0])
    low, high = rows[0], rows[-1]
    lines = [
        f"Highest lowest-DSCR-over-the-hold: {high[1]} at {high[2]['min_dscr_over_hold']} "
        f"(year-one {high[2]['year_one_dscr']}).",
        f"Lowest: {low[1]} at {low[2]['min_dscr_over_hold']} "
        f"(year-one {low[2]['year_one_dscr']}).",
    ]
    if len(rows) > 2:
        lines.append("All deals: " + "; ".join(f"{r[1]} {r[0]:.2f}x" for r in reversed(rows)) + ".")
    skipped = len(deals) - len(rows)
    if skipped:
        lines.append(f"{skipped} deal(s) have no DSCR (no debt).")
    return "\n".join(lines)


def _ranking_basis(ctx: ToolContext) -> str:
    res = _ranking(ctx)
    return (
        res["basis_note"]
        + f" Current DSCR minimum: {res['dscr_minimum']}. "
        + _treasury_line(res["treasury"])
        + "."
    )


_ANSWERS = {
    "top_deal": _top_deal,
    "dscr_gate": _dscr_gate,
    "hurdle_breakdown": _hurdle_breakdown,
    "dscr_extremes": _dscr_extremes,
    "ranking_basis": _ranking_basis,
}


def answer_preset(ctx: ToolContext, preset_id: str) -> str:
    """Raises KeyError for an unknown id; ToolError if the data isn't available."""
    fn = _ANSWERS[preset_id]
    try:
        body = fn(ctx)
    except ToolError as exc:
        return f"I can't answer that yet: {exc.payload['message']}"
    return f"{body}\n\n{DISCLAIMER}"

"""Read-only tools the chat assistant can call.

Every number the assistant may quote comes from here, and every number here
comes from the deterministic engine or the existing API logic (compute,
gather_ranked_entries, rank_risk_adjusted, the sensitivity sweep, the hurdle
table, the rent check) called in-process — never from the model, never over
HTTP. Results are compact JSON with figures pre-formatted as strings ("9.91%",
"$21,500,000", "1.33x") so a small model can copy them rather than reformat
them, and null/absent means "not available".

Small free models call tools badly, so nothing is executed until the tool
name is on the allowlist and the arguments pass strict Pydantic validation;
failures come back as structured errors the model can retry on. There are no
write tools here and the registry is the only way in.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.analysis_schemas import RiskRankRequest, SweepRequest, WeightsIn
from app.api.converters import deal_to_engine_inputs
from app.api.market_check import geographies, rent_check
from app.api.ranking_data import RANKING_BASIS_NOTE, gather_ranked_entries
from app.api.risk_rank import hurdle_table, rank_risk_adjusted
from app.api.sensitivity import sweep
from app.engine.metrics import compute
from app.models.deal import Deal

logger = logging.getLogger(__name__)

MAX_DEALS = 25
MAX_RESULT_CHARS = 6000
MAX_SWEEP_STEPS = 9

TREASURY_LABELS = {
    "fred": "live (FRED DGS10)",
    "treasury": "live (US Treasury par yield curve)",
    "fallback": "FALLBACK default - the live lookup failed, this is not a current quote",
    "override": "manual override supplied by the user",
}


# ---------------------------------------------------------------- formatting


def money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def pct(value: Decimal | None, places: int = 2) -> str | None:
    if value is None:
        return None
    return f"{value * 100:.{places}f}%"


def mult(value: Decimal | None) -> str | None:
    return None if value is None else f"{value:.2f}x"


def treasury_block(treasury) -> dict[str, Any]:
    """`treasury` is a TreasuryOut (alias-free attributes: yield_, as_of, source)."""
    return {
        "yield": pct(treasury.yield_),
        "as_of": treasury.as_of.isoformat() if treasury.as_of else None,
        "source": TREASURY_LABELS.get(treasury.source, treasury.source),
        "is_fallback": treasury.source == "fallback",
    }


# ---------------------------------------------------------------- plumbing


class ToolError(Exception):
    """A failure the model can read and react to (never a 500)."""

    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.payload: dict[str, Any] = {"error": code, "message": message, **extra}


@dataclass(frozen=True)
class UiContext:
    """What the UI had selected / configured, used as defaults when the model omits them."""

    selected_deal_ids: tuple[uuid.UUID, ...] = ()
    dscr_minimum: Decimal | None = None
    treasury_yield: Decimal | None = None
    weights: WeightsIn | None = None
    hurdle_rate: Decimal | None = None


@dataclass(frozen=True)
class ToolContext(UiContext):
    db: Session = field(kw_only=True)

    @classmethod
    def bind(cls, ui: UiContext, db: Session) -> ToolContext:
        return cls(db=db, **vars(ui))


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _unwrap(exc: HTTPException) -> ToolError:
    detail = exc.detail if isinstance(exc.detail, str) else "request rejected"
    return ToolError("not_available", detail)


def resolve_deal(db: Session, ref: str) -> Deal:
    """A deal by id, exact name or unique name fragment (case-insensitive)."""
    ref = ref.strip()
    try:
        deal = db.get(Deal, uuid.UUID(ref))
    except ValueError:
        deal = None
    else:
        if deal is None:
            raise ToolError("deal_not_found", f"No deal with id {ref}. Call list_deals.")
        return deal
    deals = list(db.scalars(select(Deal).order_by(Deal.created_at, Deal.id)))
    needle = ref.casefold()
    exact = [d for d in deals if d.name.casefold() == needle]
    matches = exact or [d for d in deals if needle and needle in d.name.casefold()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ToolError("deal_not_found", f"No deal matching '{ref}'. Call list_deals.")
    raise ToolError(
        "ambiguous_deal",
        f"'{ref}' matches several deals; use an id.",
        candidates=[{"id": str(d.id), "name": d.name} for d in matches[:5]],
    )


def _resolve_many(ctx: ToolContext, refs: list[str] | None) -> list[Deal]:
    if refs:
        deals = [resolve_deal(ctx.db, r) for r in refs]
    elif ctx.selected_deal_ids:
        deals = []
        for deal_id in ctx.selected_deal_ids:
            deal = ctx.db.get(Deal, deal_id)
            if deal is not None:
                deals.append(deal)
    else:
        deals = list(ctx.db.scalars(select(Deal).order_by(Deal.created_at, Deal.id)))
    deals = list({d.id: d for d in deals}.values())
    if not deals:
        raise ToolError("no_deals", "There are no deals to analyze.")
    return deals[:MAX_DEALS]


def _units_or_beds(deal: Deal) -> str:
    if deal.leasing_mode.value == "per_bed":
        return f"{deal.bed_count} beds"
    return f"{deal.unit_count} units"


# ---------------------------------------------------------------- tools


class NoArgs(_Args):
    pass


def list_deals(ctx: ToolContext, args: NoArgs) -> dict[str, Any]:
    deals = list(
        ctx.db.scalars(select(Deal).order_by(Deal.created_at, Deal.id).limit(MAX_DEALS + 1))
    )
    return {
        "deals": [
            {
                "id": str(d.id),
                "name": d.name,
                "sub_asset_class": d.sub_asset_class.value,
                "size": _units_or_beds(d),
                "purchase_price": money(d.purchase_price),
                "selected_in_ui": d.id in ctx.selected_deal_ids,
            }
            for d in deals[:MAX_DEALS]
        ],
        "truncated": len(deals) > MAX_DEALS,
    }


class DealArg(_Args):
    deal: str = Field(min_length=1, max_length=100)


def get_deal(ctx: ToolContext, args: DealArg) -> dict[str, Any]:
    d = resolve_deal(ctx.db, args.deal)
    rent = (
        f"{money(d.monthly_rent_per_bed)}/bed/month"
        if d.leasing_mode.value == "per_bed"
        else f"{money(d.monthly_rent_per_unit)}/unit/month"
    )
    out: dict[str, Any] = {
        "id": str(d.id),
        "name": d.name,
        "sub_asset_class": d.sub_asset_class.value,
        "leasing_mode": d.leasing_mode.value,
        "size": _units_or_beds(d),
        "rent": rent,
        "vacancy_rate": pct(d.vacancy_rate),
        "credit_loss_rate": pct(d.credit_loss_rate),
        "other_income_annual": money(d.other_income_annual),
        "opex_annual": money(d.opex_annual),
        "management_fee_rate": pct(d.management_fee_rate),
        "rent_growth_rate": pct(d.rent_growth_rate),
        "expense_growth_rate": pct(d.expense_growth_rate),
        "purchase_price": money(d.purchase_price),
        "closing_costs": money(d.closing_costs),
        "hold_period_years": d.hold_period_years,
        "exit_cap_rate": pct(d.exit_cap_rate),
        "selling_costs_rate": pct(d.selling_costs_rate),
    }
    if d.capital_stack:
        out["capital_stack"] = [
            {
                "type": layer.get("type"),
                "label": layer.get("label"),
                "amount": money(Decimal(str(layer["amount"]))),
                "interest_rate": (
                    pct(Decimal(str(layer["interest_rate"])))
                    if layer.get("interest_rate") is not None
                    else None
                ),
            }
            for layer in d.capital_stack[:6]
        ]
    else:
        out["loan"] = {
            "amount": money(d.loan_amount),
            "interest_rate": pct(d.interest_rate),
            "amortization_years": d.amortization_years,
        }
    return out


def get_metrics(ctx: ToolContext, args: DealArg) -> dict[str, Any]:
    d = resolve_deal(ctx.db, args.deal)
    m = compute(deal_to_engine_inputs(d))
    y1 = m.annual_cash_flows[0] if m.annual_cash_flows else None
    return {
        "deal": d.name,
        "id": str(d.id),
        "year_one_noi": money(m.year_one_noi),
        "going_in_cap_rate": pct(m.going_in_cap_rate),
        "year_one_dscr": mult(m.year_one_dscr),
        "year_one_senior_dscr": mult(m.year_one_senior_dscr),
        "min_dscr_over_hold": mult(m.min_dscr),
        "dscr_by_year": [
            mult(cf.noi / cf.debt_service) if cf.debt_service > 0 else None
            for cf in m.annual_cash_flows
        ],
        "debt_yield": pct(m.debt_yield),
        "cash_on_cash_year_one": pct(m.cash_on_cash),
        "unlevered_irr_net_of_costs": pct(m.unlevered_irr),
        "unlevered_irr_before_costs_ranking_basis": pct(m.unlevered_irr_before_costs),
        "levered_irr_reference_only": pct(m.levered_irr),
        "equity_multiple": mult(m.equity_multiple),
        "equity_invested": money(m.equity_invested),
        "exit_value": money(m.exit_value),
        "loan_balance_at_exit": money(m.loan_balance_at_exit),
        "year_one": (
            None
            if y1 is None
            else {
                "gpr": money(y1.gpr),
                "vacancy_loss": money(y1.vacancy_loss),
                "other_income": money(y1.other_income),
                "egi": money(y1.egi),
                "opex": money(y1.opex),
                "turnover_expense": money(y1.turnover_expense),
                "noi": money(y1.noi),
                "debt_service": money(y1.debt_service),
                "levered_cash_flow": money(y1.levered_cash_flow),
            }
        ),
        "note": "A null figure means it is not available (e.g. no debt, or IRR did not converge).",
    }


class RankDealsArgs(_Args):
    # Decimal fraction (0.07 = 7%); defaults to the hurdle rate set in the UI.
    hurdle_rate: Decimal | None = Field(default=None, ge=-1, le=1)
    deal_ids: list[str] | None = Field(default=None, max_length=MAX_DEALS)


def rank_deals(ctx: ToolContext, args: RankDealsArgs) -> dict[str, Any]:
    hurdle = args.hurdle_rate if args.hurdle_rate is not None else ctx.hurdle_rate
    if hurdle is None:
        raise ToolError("missing_argument", "hurdle_rate is required (a fraction, 0.07 = 7%).")
    deals = _resolve_many(ctx, args.deal_ids)
    try:
        entries = gather_ranked_entries(ctx.db, [d.id for d in deals], hurdle)
    except HTTPException as exc:
        raise _unwrap(exc) from exc
    return {
        "hurdle_rate": pct(hurdle),
        "ranking": [
            {
                "rank": e.rank,
                "deal": e.deal.name,
                "unlevered_irr": pct(e.metrics.unlevered_irr),
                "spread_vs_hurdle": pct(e.spread) if e.spread.is_finite() else None,
            }
            for e in entries
        ],
        "basis_note": RANKING_BASIS_NOTE,
    }


class WeightsArg(_Args):
    irr: Decimal = Field(ge=0)
    cash_flow: Decimal = Field(ge=0)
    risk: Decimal = Field(ge=0)


class RiskRankArgs(_Args):
    deal_ids: list[str] | None = Field(default=None, max_length=MAX_DEALS)
    dscr_minimum: Decimal | None = Field(default=None, ge=0, le=5)
    treasury_yield: Decimal | None = Field(default=None, ge=0, le=1)
    weights: WeightsArg | None = None


def risk_rank(ctx: ToolContext, args: RiskRankArgs) -> dict[str, Any]:
    deals = _resolve_many(ctx, args.deal_ids)
    weights = args.weights or ctx.weights
    kwargs: dict[str, Any] = {"deal_ids": [d.id for d in deals]}
    dscr = args.dscr_minimum if args.dscr_minimum is not None else ctx.dscr_minimum
    if dscr is not None:
        kwargs["dscr_minimum"] = dscr
    treasury = args.treasury_yield if args.treasury_yield is not None else ctx.treasury_yield
    if treasury is not None:
        kwargs["treasury_yield"] = treasury
    if weights is not None:
        kwargs["weights"] = WeightsIn(
            irr=weights.irr, cash_flow=weights.cash_flow, risk=weights.risk
        )
    try:
        res = rank_risk_adjusted(RiskRankRequest(**kwargs), ctx.db)
    except HTTPException as exc:
        raise _unwrap(exc) from exc
    return {
        "treasury": treasury_block(res.treasury),
        "dscr_minimum": mult(res.dscr_minimum),
        "weights": {
            "irr": pct(res.weights.irr, 0),
            "cash_flow": pct(res.weights.cash_flow, 0),
            "risk": pct(res.weights.risk, 0),
        },
        "ranked": [
            {
                "rank": r.rank,
                "deal": r.deal.name,
                "score": f"{r.score:.1f}",
                "spread_vs_hurdle": pct(r.spread),
                "unlevered_irr_before_costs": pct(r.metrics.unlevered_irr_before_costs),
                "hurdle": {
                    "total": pct(r.hurdle.total),
                    "treasury": pct(r.hurdle.treasury_yield),
                    "cap_rate_spread": f"{r.hurdle.spread_bps} bps",
                    "noi_growth": pct(r.hurdle.noi_growth),
                    "sub_asset_class": r.hurdle.sub_asset_class,
                },
                "min_dscr": mult(r.metrics.min_dscr),
                "ltv": pct(r.ltv),
                "factor_scores_0_to_100": {
                    "irr": f"{r.factors.irr:.0f}",
                    "cash_flow": f"{r.factors.cash_flow:.0f}",
                    "risk": f"{r.factors.risk:.0f}",
                },
                "warnings": r.warnings,
            }
            for r in res.ranked
        ],
        "excluded": [
            {
                "deal": e.deal.name,
                "reason": e.reason,
                "min_dscr": mult(e.metrics.min_dscr),
            }
            for e in res.excluded
        ],
        "basis_note": res.basis_note,
    }


class SensitivityArgs(_Args):
    deal: str = Field(min_length=1, max_length=100)
    variable: Literal["exit_cap_rate", "rent_growth_rate"]
    low: Decimal | None = Field(default=None, ge=-1, le=1)
    high: Decimal | None = Field(default=None, ge=-1, le=1)
    steps: int = Field(default=5, ge=2, le=MAX_SWEEP_STEPS)


def sensitivity(ctx: ToolContext, args: SensitivityArgs) -> dict[str, Any]:
    d = resolve_deal(ctx.db, args.deal)
    try:
        res = sweep(
            d.id,
            SweepRequest(variable=args.variable, low=args.low, high=args.high, steps=args.steps),
            ctx.db,
        )
    except HTTPException as exc:
        raise _unwrap(exc) from exc
    return {
        "deal": d.name,
        "variable": res.variable,
        "base_value": pct(res.base_value),
        "points": [
            {
                res.variable: pct(p.value),
                "unlevered_irr": pct(p.unlevered_irr),
                "levered_irr": pct(p.levered_irr),
                "min_dscr": mult(p.min_dscr),
                "exit_value": money(p.exit_value),
            }
            for p in res.points
        ],
        "note": "Single-variable sweep; every other input is held at the deal's value.",
    }


class MarketCheckArgs(_Args):
    deal: str = Field(min_length=1, max_length=100)
    geography: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=50)


def market_check(ctx: ToolContext, args: MarketCheckArgs) -> dict[str, Any]:
    d = resolve_deal(ctx.db, args.deal)
    if not args.geography:
        geos = geographies(ctx.db)
        return {
            "message": "Pass one of these geographies to compare the deal's rent to market.",
            "geographies": [{"geography": g.geography, "source": g.source} for g in geos[:30]],
        }
    try:
        r = rent_check(d.id, args.geography, args.source, ctx.db)
    except HTTPException as exc:
        raise _unwrap(exc) from exc
    return {
        "deal": d.name,
        "status": r.status,
        "geography": r.geography,
        "deal_rent": money(r.deal_rent),
        "market_rent": money(r.market_rent),
        "market_period": r.market_period.isoformat() if r.market_period else None,
        "source": r.source,
        "variance_vs_market": pct(r.variance),
        "market_yoy_growth": pct(r.market_yoy_growth),
        "deal_rent_growth": pct(r.deal_rent_growth),
        "note": r.note,
    }


def get_hurdles(ctx: ToolContext, args: NoArgs) -> dict[str, Any]:
    try:
        table = hurdle_table(ctx.db)
    except HTTPException as exc:
        raise _unwrap(exc) from exc
    return {
        "treasury": treasury_block(table.treasury),
        "formula": "hurdle = 10-Year Treasury + sub-class cap-rate spread + stabilized NOI growth",
        "hurdles": [
            {
                "sub_asset_class": h.sub_asset_class,
                "treasury": pct(h.treasury_yield),
                "cap_rate_spread": f"{h.spread_bps} bps",
                "cap_rate": pct(h.cap_rate),
                "noi_growth": pct(h.noi_growth),
                "total_hurdle": pct(h.total),
                "survey": f"{h.survey_source} {h.survey_quarter}",
            }
            for h in table.hurdles
        ],
    }


# ---------------------------------------------------------------- registry


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[_Args]
    fn: Callable[[ToolContext, Any], dict[str, Any]]
    status: str  # shown to the user while the tool runs
    parameters: dict[str, Any] = field(default_factory=dict)

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", **self.parameters},
            },
        }


_DEAL = {"type": "string", "description": "deal id or name (from list_deals)"}
_DEAL_IDS = {
    "type": "array",
    "items": {"type": "string"},
    "description": "deal ids or names; omit to use the deals selected in the UI",
}

TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "list_deals",
            "List all deals with id, name, class and price.",
            NoArgs,
            list_deals,
            "Listing deals",
            {"properties": {}},
        ),
        Tool(
            "get_deal",
            "Show one deal's inputs (rent, vacancy, opex, price, financing, exit assumptions).",
            DealArg,
            get_deal,
            "Looking up deal",
            {"properties": {"deal": _DEAL}, "required": ["deal"]},
        ),
        Tool(
            "get_metrics",
            "Computed metrics for one deal: NOI, cap rate, DSCR, IRRs, equity multiple, "
            "year-one waterfall.",
            DealArg,
            get_metrics,
            "Computing deal metrics",
            {"properties": {"deal": _DEAL}, "required": ["deal"]},
        ),
        Tool(
            "rank_deals",
            "Simple ranking by unlevered IRR minus ONE flat hurdle rate (default: the UI's).",
            RankDealsArgs,
            rank_deals,
            "Ranking deals",
            {
                "properties": {
                    "hurdle_rate": {"type": "number", "description": "fraction, 0.07 = 7%"},
                    "deal_ids": _DEAL_IDS,
                },
            },
        ),
        Tool(
            "risk_rank",
            "Risk-adjusted ranking: DSCR gate exclusions, each deal's own hurdle, optional "
            "weights. Use for 'why is X ranked below Y' and 'who was excluded'.",
            RiskRankArgs,
            risk_rank,
            "Running risk-adjusted ranking",
            {
                "properties": {
                    "deal_ids": _DEAL_IDS,
                    "dscr_minimum": {"type": "number", "description": "e.g. 1.25"},
                    "treasury_yield": {"type": "number", "description": "fraction; omit for live"},
                    "weights": {
                        "type": "object",
                        "properties": {
                            "irr": {"type": "number"},
                            "cash_flow": {"type": "number"},
                            "risk": {"type": "number"},
                        },
                        "required": ["irr", "cash_flow", "risk"],
                    },
                }
            },
        ),
        Tool(
            "sensitivity",
            "Sweep exit cap rate or rent growth for one deal and show IRR/DSCR at each value.",
            SensitivityArgs,
            sensitivity,
            "Running sensitivity",
            {
                "properties": {
                    "deal": _DEAL,
                    "variable": {"type": "string", "enum": ["exit_cap_rate", "rent_growth_rate"]},
                    "low": {"type": "number", "description": "fraction; optional"},
                    "high": {"type": "number", "description": "fraction; optional"},
                    "steps": {"type": "integer", "description": f"2-{MAX_SWEEP_STEPS}"},
                },
                "required": ["deal", "variable"],
            },
        ),
        Tool(
            "market_check",
            "Compare a deal's rent to loaded market rent data. Omit geography to list options.",
            MarketCheckArgs,
            market_check,
            "Checking market rents",
            {
                "properties": {
                    "deal": _DEAL,
                    "geography": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["deal"],
            },
        ),
        Tool(
            "get_hurdles",
            "The risk-adjusted hurdle breakdown per sub-asset class, with the Treasury "
            "yield and whether it is live or a fallback.",
            NoArgs,
            get_hurdles,
            "Looking up hurdles",
            {"properties": {}},
        ),
    ]
}


def _error_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"))


def run_tool(ctx: ToolContext, name: str, raw_args: str | None) -> tuple[str, bool]:
    """Validate and execute one tool call. Returns (JSON string for the model, ok).

    Never raises: unknown tools, malformed JSON, bad arguments and engine
    errors all come back as {"error": ...} so the model can retry.
    """
    tool = TOOLS.get(name)
    if tool is None:
        return (
            _error_result(
                {
                    "error": "unknown_tool",
                    "message": f"'{name}' is not a tool.",
                    "available_tools": sorted(TOOLS),
                }
            ),
            False,
        )
    try:
        parsed = json.loads(raw_args) if raw_args and raw_args.strip() else {}
    except json.JSONDecodeError:
        return (
            _error_result(
                {"error": "arguments_not_valid_json", "message": "Arguments must be a JSON object."}
            ),
            False,
        )
    if not isinstance(parsed, dict):
        return (
            _error_result(
                {"error": "arguments_not_valid_json", "message": "Arguments must be a JSON object."}
            ),
            False,
        )
    try:
        args = tool.args_model.model_validate(parsed)
    except ValidationError as exc:
        return (
            _error_result(
                {
                    "error": "invalid_arguments",
                    "tool": name,
                    "problems": [
                        {
                            "field": ".".join(str(p) for p in e["loc"]) or "(root)",
                            "problem": e["msg"],
                        }
                        for e in exc.errors()[:5]
                    ],
                    "expected_parameters": tool.spec()["function"]["parameters"],
                }
            ),
            False,
        )
    try:
        result = tool.fn(ctx, args)
    except ToolError as exc:
        return _error_result(exc.payload), False
    except HTTPException as exc:
        return _error_result(_unwrap(exc).payload), False
    except Exception:  # an engine/DB failure must not kill the stream
        logger.exception("chat tool %s failed", name)
        return (
            _error_result(
                {
                    "error": "tool_failed",
                    "message": "The lookup failed; say the data is unavailable.",
                }
            ),
            False,
        )
    text = json.dumps(result, separators=(",", ":"))
    if len(text) > MAX_RESULT_CHARS:
        return (
            _error_result(
                {
                    "error": "result_too_large",
                    "message": "Result too large; call again for fewer deals or fewer steps.",
                }
            ),
            False,
        )
    return text, True

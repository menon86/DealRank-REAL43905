"""Headline metrics. See docs/build-plan.md 1.6.

This is the only module in app/engine that touches float: numpy-financial's
IRR solver requires it. Every other value stays Decimal all the way
through. Money in, Decimal out; the float boundary is contained to
_irr() below.
"""

from __future__ import annotations

import math
from decimal import Decimal

import numpy_financial as npf

from app.engine.types import DealInputs, DealMetrics
from app.engine.waterfall import WaterfallResult, project


def _irr(cash_flows: list[Decimal]) -> Decimal | None:
    """Wraps numpy-financial's IRR, converting to/from Decimal only here.
    Returns None rather than raising when the solver doesn't converge
    (numpy-financial returns nan in that case).
    """
    float_flows = [float(cf) for cf in cash_flows]
    try:
        result = npf.irr(float_flows)
    except Exception:
        return None
    if result is None or (isinstance(result, float) and math.isnan(result)):
        return None
    return Decimal(str(result))


def going_in_cap_rate(deal: DealInputs, year_one_noi: Decimal) -> Decimal:
    return year_one_noi / deal.purchase_price


def dscr(noi: Decimal, debt_service: Decimal) -> Decimal | None:
    """NOI / debt service for one year. None (not a division error) when
    debt service is zero — an all-cash deal has no DSCR to report.
    """
    if debt_service == 0:
        return None
    return noi / debt_service


def equity_invested(deal: DealInputs) -> Decimal:
    return deal.purchase_price + deal.closing_costs - deal.loan_amount


def compute(deal: DealInputs) -> DealMetrics:
    result: WaterfallResult = project(deal)
    flows = result.annual_cash_flows

    year_one = flows[0]
    equity = equity_invested(deal)

    cap_rate = going_in_cap_rate(deal, year_one.noi)
    year_one_dscr = dscr(year_one.noi, year_one.debt_service)
    cash_on_cash = (year_one.levered_cash_flow / equity) if equity != 0 else None

    # Levered stream: initial equity outlay, then each year's levered cash
    # flow, with the final year's net sale proceeds (post debt payoff)
    # added to the terminal cash flow.
    levered_stream = [-equity] + [cf.levered_cash_flow for cf in flows]
    levered_stream[-1] += result.net_sale_proceeds
    levered_irr = _irr(levered_stream)

    # Unlevered stream: full purchase price + closing costs as the outlay,
    # no debt anywhere, terminal proceeds are exit value less selling
    # costs only (no loan payoff, since there is no loan in this stream).
    unlevered_outlay = deal.purchase_price + deal.closing_costs
    unlevered_exit_proceeds = result.exit_value - (result.exit_value * deal.selling_costs_rate)
    unlevered_stream = [-unlevered_outlay] + [cf.unlevered_cash_flow for cf in flows]
    unlevered_stream[-1] += unlevered_exit_proceeds
    unlevered_irr = _irr(unlevered_stream)

    total_levered_cf = sum((cf.levered_cash_flow for cf in flows), Decimal("0"))
    equity_multiple = (
        (total_levered_cf + result.net_sale_proceeds) / equity if equity != 0 else None
    )

    return DealMetrics(
        annual_cash_flows=flows,
        year_one_noi=year_one.noi,
        going_in_cap_rate=cap_rate,
        year_one_dscr=year_one_dscr,
        cash_on_cash=cash_on_cash,
        unlevered_irr=unlevered_irr,
        levered_irr=levered_irr,
        equity_multiple=equity_multiple,
        exit_value=result.exit_value,
        net_sale_proceeds=result.net_sale_proceeds,
    )

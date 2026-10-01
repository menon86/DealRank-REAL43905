"""One test per per-deal formula in the v1 scope, each recomputed from the
deal's raw inputs (via tests/engine/independent_math.py, not app.engine)
and compared against what compute() reports. These cover the figures the
comparison view shows beyond the golden Year 1 cases: equity invested,
the multi-year NOI and levered cash flow, the exit arithmetic, and both
IRR streams as the scope document writes them.
"""

from decimal import Decimal

import numpy_financial as npf
import pytest

from app.engine.debt import monthly_payment
from app.engine.metrics import compute
from tests.engine.fixtures import ALL_SEED_DEALS
from tests.engine.independent_math import closed_form_balance, forward_noi

CENT = Decimal("0.01")
IDS = ["student_housing", "suburban_garden", "urban_midrise"]


def approx_equal(a: Decimal, b: Decimal, tolerance: Decimal = CENT) -> bool:
    return abs(a - b) <= tolerance


@pytest.mark.parametrize("deal", ALL_SEED_DEALS, ids=IDS)
def test_equity_invested_is_price_plus_closing_less_loan(deal):
    m = compute(deal)
    assert m.equity_invested == deal.purchase_price + deal.closing_costs - deal.loan_amount


@pytest.mark.parametrize("deal", ALL_SEED_DEALS, ids=IDS)
def test_noi_every_year_grows_rent_and_expenses_separately(deal):
    m = compute(deal)
    for cf in m.annual_cash_flows:
        assert approx_equal(cf.noi, forward_noi(deal, cf.year)), f"year {cf.year}"


@pytest.mark.parametrize("deal", ALL_SEED_DEALS, ids=IDS)
def test_going_in_cap_rate_and_dscr(deal):
    m = compute(deal)
    year_one = m.annual_cash_flows[0]
    assert m.going_in_cap_rate == year_one.noi / deal.purchase_price
    annual_debt_service = (
        monthly_payment(deal.loan_amount, deal.interest_rate, deal.amortization_years) * 12
    )
    assert approx_equal(year_one.debt_service, annual_debt_service)
    assert m.year_one_dscr == year_one.noi / year_one.debt_service


@pytest.mark.parametrize("deal", ALL_SEED_DEALS, ids=IDS)
def test_levered_cash_flow_and_cash_on_cash(deal):
    m = compute(deal)
    for cf in m.annual_cash_flows:
        assert cf.levered_cash_flow == cf.noi - cf.debt_service
    assert m.cash_on_cash == m.annual_cash_flows[0].levered_cash_flow / m.equity_invested


@pytest.mark.parametrize("deal", ALL_SEED_DEALS, ids=IDS)
def test_exit_value_and_net_sale_proceeds(deal):
    m = compute(deal)
    n = deal.hold_period_years

    assert approx_equal(m.forward_noi, forward_noi(deal, n + 1))
    assert m.exit_value == m.forward_noi / deal.exit_cap_rate
    assert m.selling_costs == m.exit_value * deal.selling_costs_rate

    balance = closed_form_balance(
        deal.loan_amount, deal.interest_rate, deal.amortization_years, n * 12
    )
    assert approx_equal(m.loan_balance_at_exit, balance)
    assert m.net_sale_proceeds == m.exit_value - m.selling_costs - m.loan_balance_at_exit


def _npv(rate: Decimal, stream: list[Decimal]) -> float:
    return float(npf.npv(float(rate), [float(cf) for cf in stream]))


@pytest.mark.parametrize("deal", ALL_SEED_DEALS, ids=IDS)
def test_irr_streams_match_scope_definitions(deal):
    """Each reported IRR must zero the NPV of the stream exactly as the
    scope defines it, so a wrong stream can't pass by coincidence."""
    m = compute(deal)
    flows = m.annual_cash_flows

    levered = [-m.equity_invested] + [cf.levered_cash_flow for cf in flows]
    levered[-1] += m.net_sale_proceeds
    assert abs(_npv(m.levered_irr, levered)) < 1.0

    unlevered = [-(deal.purchase_price + deal.closing_costs)] + [cf.noi for cf in flows]
    unlevered[-1] += m.exit_value - m.selling_costs
    assert abs(_npv(m.unlevered_irr, unlevered)) < 1.0


@pytest.mark.parametrize("deal", ALL_SEED_DEALS, ids=IDS)
def test_equity_multiple_is_total_distributions_over_equity(deal):
    m = compute(deal)
    total = sum((cf.levered_cash_flow for cf in m.annual_cash_flows), Decimal("0"))
    assert m.total_distributions == total + m.net_sale_proceeds
    assert m.equity_multiple == m.total_distributions / m.equity_invested

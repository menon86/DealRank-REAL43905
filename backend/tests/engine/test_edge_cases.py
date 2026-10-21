"""See docs/build-plan.md 2.3 — zero vacancy; 100% turnover; all-cash
(DSCR undefined rather than a division error); a negative-cash-flow deal;
a one-year hold; a non-converging IRR.
"""

from dataclasses import replace
from decimal import Decimal

from app.engine.debt import amortization_schedule
from app.engine.metrics import compute
from app.engine.types import DealInputs, LeasingMode, SubAssetClass
from app.engine.waterfall import project

BASE_DEAL = DealInputs(
    name="Edge Case Base Deal",
    sub_asset_class=SubAssetClass.SUBURBAN_GARDEN,
    leasing_mode=LeasingMode.PER_UNIT,
    unit_count=100,
    monthly_rent_per_unit=Decimal("1000.00"),
    bed_count=None,
    monthly_rent_per_bed=None,
    vacancy_rate=Decimal("0.05"),
    other_income_annual=Decimal("10000.00"),
    opex_annual=Decimal("300000.00"),
    expense_growth_rate=Decimal("0.03"),
    rent_growth_rate=Decimal("0.03"),
    lease_expiration_month=6,
    turnover_cost_per_unit_or_bed=Decimal("500.00"),
    annual_turnover_rate=Decimal("0.5"),
    purchase_price=Decimal("10000000.00"),
    closing_costs=Decimal("200000.00"),
    loan_amount=Decimal("6500000.00"),
    interest_rate=Decimal("0.06"),
    amortization_years=30,
    hold_period_years=10,
    exit_cap_rate=Decimal("0.06"),
    selling_costs_rate=Decimal("0.02"),
)


def test_zero_vacancy():
    deal = replace(BASE_DEAL, vacancy_rate=Decimal("0"))
    result = project(deal)
    year_one = result.annual_cash_flows[0]
    assert year_one.vacancy_loss == Decimal("0")
    assert year_one.egi == year_one.gpr + year_one.other_income


def test_full_turnover():
    deal = replace(BASE_DEAL, annual_turnover_rate=Decimal("1.0"))
    result = project(deal)
    year_one = result.annual_cash_flows[0]
    expected_turnover = deal.turnover_cost_per_unit_or_bed * deal.unit_count
    assert year_one.turnover_expense == expected_turnover


def test_all_cash_deal_has_no_dscr():
    """DSCR is undefined, not a division error, when there's no debt."""
    deal = replace(BASE_DEAL, loan_amount=Decimal("0"))
    metrics = compute(deal)
    assert metrics.year_one_dscr is None

    schedule = amortization_schedule(deal)
    assert all(row.debt_service == 0 for row in schedule)
    assert all(row.ending_balance == 0 for row in schedule)


def test_all_cash_deal_computes_without_error():
    deal = replace(BASE_DEAL, loan_amount=Decimal("0"))
    metrics = compute(deal)
    # Unlevered and levered IRR are identical with no debt in the picture.
    assert metrics.unlevered_irr == metrics.levered_irr


def test_negative_cash_flow_deal():
    """Heavy leverage and thin NOI produce negative levered cash flow in
    at least one year without the engine raising.
    """
    deal = replace(
        BASE_DEAL,
        loan_amount=Decimal("9500000.00"),
        interest_rate=Decimal("0.09"),
        amortization_years=15,
    )
    metrics = compute(deal)
    assert any(cf.levered_cash_flow < 0 for cf in metrics.annual_cash_flows)


def test_one_year_hold():
    deal = replace(BASE_DEAL, hold_period_years=1)
    metrics = compute(deal)
    assert len(metrics.annual_cash_flows) == 1
    assert metrics.unlevered_irr is not None
    assert metrics.levered_irr is not None


def test_non_converging_irr_returns_none_not_raises():
    """A cash-flow stream with no sign change (e.g. a deal that never
    returns any positive cash flow) shouldn't converge to an IRR; the
    engine returns None rather than raising.
    """
    deal = replace(
        BASE_DEAL,
        opex_annual=Decimal("50000000.00"),  # dwarfs revenue every year
        loan_amount=Decimal("0"),
        hold_period_years=3,
        exit_cap_rate=Decimal("0.06"),
    )
    metrics = compute(deal)
    assert metrics.unlevered_irr is None
    assert metrics.levered_irr is None


# ------------------------------------------------- guards on impossible structures


def _layer(layer_type, amount, **kwargs):
    from app.engine.types import FinancingLayer

    return FinancingLayer(layer_type=layer_type, amount=Decimal(amount), **kwargs)


def test_balloon_inside_hold_gives_no_irr_rather_than_an_arbitrary_root():
    from app.engine.types import LayerType

    stack = (
        _layer(
            LayerType.BRIDGE_DEBT_FUND,
            "6500000",
            interest_rate=Decimal("0.08"),
            io_months=36,
            term_years=3,
        ),
        _layer(LayerType.SPONSOR_GP, "1"),
    )
    metrics = compute(replace(BASE_DEAL, capital_stack=stack, hold_period_years=5))
    assert any(cf.balloon_payment > 0 for cf in metrics.annual_cash_flows)
    # The balloon turns one year's cash flow negative between positive years.
    assert min(cf.levered_cash_flow for cf in metrics.annual_cash_flows) < 0
    assert metrics.levered_irr is None
    assert metrics.unlevered_irr is not None  # financing doesn't touch it


def test_negative_forward_noi_exit_value_is_floored_at_zero():
    deal = replace(BASE_DEAL, opex_annual=Decimal("5000000.00"))
    metrics = compute(deal)
    assert metrics.forward_noi < 0
    assert metrics.exit_value == 0


def test_no_cash_on_cash_or_multiple_when_common_equity_is_not_positive():
    over = replace(BASE_DEAL, loan_amount=Decimal("10500000.00"))
    m = compute(over)
    assert m.equity_invested < 0
    assert m.cash_on_cash is None and m.equity_multiple is None


def test_new_ranking_metrics():
    metrics = compute(BASE_DEAL)
    assert metrics.min_dscr == min(cf.noi / cf.debt_service for cf in metrics.annual_cash_flows)
    assert metrics.debt_yield == metrics.year_one_noi / BASE_DEAL.loan_amount
    assert metrics.unlevered_cash_yield == metrics.year_one_noi / Decimal("10200000.00")
    # Costs only ever lower an IRR.
    assert metrics.unlevered_irr_before_costs > metrics.unlevered_irr


def test_all_cash_has_no_min_dscr_or_debt_yield():
    metrics = compute(replace(BASE_DEAL, loan_amount=Decimal("0")))
    assert metrics.min_dscr is None and metrics.debt_yield is None


def test_engine_rejects_impossible_inputs_even_without_the_api():
    import pytest

    for change in (
        {"monthly_rent_per_unit": Decimal("-1")},
        {"vacancy_rate": Decimal("1.2")},
        {"vacancy_rate": Decimal("-0.1")},
        {"opex_annual": Decimal("-1")},
        {"purchase_price": Decimal("0")},
        {"closing_costs": Decimal("-1")},
        {"exit_cap_rate": Decimal("0")},
        {"selling_costs_rate": Decimal("1")},
        {"rent_growth_rate": Decimal("-1")},
        {"expense_growth_rate": Decimal("-0.02")},
        {"annual_turnover_rate": Decimal("1.5")},
        {"hold_period_years": 0},
        {"credit_loss_rate": Decimal("-0.01")},
    ):
        with pytest.raises(ValueError):
            replace(BASE_DEAL, **change)

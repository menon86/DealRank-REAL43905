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

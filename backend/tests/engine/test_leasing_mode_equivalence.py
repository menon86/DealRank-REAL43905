"""See docs/build-plan.md 2.2 — per-unit and per-bed inputs that should
agree do agree, at EGI and at every metric downstream.
"""

from decimal import Decimal

from app.engine.metrics import compute
from app.engine.types import DealInputs, LeasingMode, SubAssetClass
from app.engine.waterfall import project

BASE_KWARGS = dict(
    name="Equivalence Test Deal",
    sub_asset_class=SubAssetClass.SUBURBAN_GARDEN,
    vacancy_rate=Decimal("0.05"),
    other_income_annual=Decimal("20000.00"),
    opex_annual=Decimal("400000.00"),
    expense_growth_rate=Decimal("0.03"),
    rent_growth_rate=Decimal("0.03"),
    lease_expiration_month=6,
    turnover_cost_per_unit_or_bed=Decimal("600.00"),
    annual_turnover_rate=Decimal("0.5"),
    purchase_price=Decimal("15000000.00"),
    closing_costs=Decimal("300000.00"),
    loan_amount=Decimal("9750000.00"),
    interest_rate=Decimal("0.06"),
    amortization_years=30,
    hold_period_years=10,
    exit_cap_rate=Decimal("0.06"),
    selling_costs_rate=Decimal("0.02"),
)


def _per_unit_deal(count: int, monthly_rent: Decimal) -> DealInputs:
    return DealInputs(
        leasing_mode=LeasingMode.PER_UNIT,
        unit_count=count,
        monthly_rent_per_unit=monthly_rent,
        bed_count=None,
        monthly_rent_per_bed=None,
        **BASE_KWARGS,
    )


def _per_bed_deal(count: int, monthly_rent: Decimal) -> DealInputs:
    return DealInputs(
        leasing_mode=LeasingMode.PER_BED,
        unit_count=None,
        monthly_rent_per_unit=None,
        bed_count=count,
        monthly_rent_per_bed=monthly_rent,
        **BASE_KWARGS,
    )


def test_identical_gpr_produces_identical_egi():
    # 150 units at $1,200/mo and 150 "beds" at $1,200/mo describe the same
    # GPR (count x rate x 12 either way), so EGI must match exactly.
    per_unit = _per_unit_deal(150, Decimal("1200.00"))
    per_bed = _per_bed_deal(150, Decimal("1200.00"))

    unit_result = project(per_unit)
    bed_result = project(per_bed)

    assert unit_result.annual_cash_flows[0].egi == bed_result.annual_cash_flows[0].egi
    assert unit_result.annual_cash_flows[0].gpr == bed_result.annual_cash_flows[0].gpr


def test_identical_gpr_produces_identical_metrics_downstream():
    per_unit = _per_unit_deal(150, Decimal("1200.00"))
    per_bed = _per_bed_deal(150, Decimal("1200.00"))

    unit_metrics = compute(per_unit)
    bed_metrics = compute(per_bed)

    assert unit_metrics.year_one_noi == bed_metrics.year_one_noi
    assert unit_metrics.going_in_cap_rate == bed_metrics.going_in_cap_rate
    assert unit_metrics.year_one_dscr == bed_metrics.year_one_dscr
    assert unit_metrics.cash_on_cash == bed_metrics.cash_on_cash
    assert unit_metrics.unlevered_irr == bed_metrics.unlevered_irr
    assert unit_metrics.levered_irr == bed_metrics.levered_irr
    assert unit_metrics.equity_multiple == bed_metrics.equity_multiple
    assert unit_metrics.exit_value == bed_metrics.exit_value

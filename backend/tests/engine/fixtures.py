"""DealInputs for the three seed deals in backend/seed.py, mirrored here so
engine tests don't need a database. Keep these in sync with seed.py by
hand — SEED_DEALS there builds ORM rows; these build the engine's plain
DealInputs from the identical numbers.

The hand-derivation these golden cases are checked against lives in
docs/golden-case-derivation.md.
"""

from decimal import Decimal

from app.engine.types import DealInputs, LeasingMode, SubAssetClass

STUDENT_HOUSING = DealInputs(
    name="Campus View Student Housing",
    sub_asset_class=SubAssetClass.STUDENT_HOUSING,
    leasing_mode=LeasingMode.PER_BED,
    unit_count=None,
    monthly_rent_per_unit=None,
    bed_count=240,
    monthly_rent_per_bed=Decimal("750.00"),
    vacancy_rate=Decimal("0.06"),
    other_income_annual=Decimal("36000.00"),
    opex_annual=Decimal("620000.00"),
    expense_growth_rate=Decimal("0.03"),
    rent_growth_rate=Decimal("0.03"),
    lease_expiration_month=8,
    turnover_cost_per_unit_or_bed=Decimal("350.00"),
    annual_turnover_rate=Decimal("0.85"),
    purchase_price=Decimal("21500000.00"),
    closing_costs=Decimal("430000.00"),
    loan_amount=Decimal("14000000.00"),
    interest_rate=Decimal("0.0625"),
    amortization_years=30,
    hold_period_years=7,
    exit_cap_rate=Decimal("0.058"),
    selling_costs_rate=Decimal("0.02"),
)

SUBURBAN_GARDEN = DealInputs(
    name="Willowbrook Suburban Garden",
    sub_asset_class=SubAssetClass.SUBURBAN_GARDEN,
    leasing_mode=LeasingMode.PER_UNIT,
    unit_count=180,
    monthly_rent_per_unit=Decimal("1450.00"),
    bed_count=None,
    monthly_rent_per_bed=None,
    vacancy_rate=Decimal("0.05"),
    other_income_annual=Decimal("54000.00"),
    opex_annual=Decimal("980000.00"),
    expense_growth_rate=Decimal("0.03"),
    rent_growth_rate=Decimal("0.025"),
    lease_expiration_month=6,
    turnover_cost_per_unit_or_bed=Decimal("900.00"),
    annual_turnover_rate=Decimal("0.55"),
    purchase_price=Decimal("28800000.00"),
    closing_costs=Decimal("576000.00"),
    loan_amount=Decimal("18700000.00"),
    interest_rate=Decimal("0.06"),
    amortization_years=30,
    hold_period_years=10,
    exit_cap_rate=Decimal("0.055"),
    selling_costs_rate=Decimal("0.02"),
)

URBAN_MIDRISE = DealInputs(
    name="Meridian Urban Mid-Rise",
    sub_asset_class=SubAssetClass.URBAN_MIDRISE,
    leasing_mode=LeasingMode.PER_UNIT,
    unit_count=95,
    monthly_rent_per_unit=Decimal("2100.00"),
    bed_count=None,
    monthly_rent_per_bed=None,
    vacancy_rate=Decimal("0.07"),
    other_income_annual=Decimal("42000.00"),
    opex_annual=Decimal("870000.00"),
    expense_growth_rate=Decimal("0.03"),
    rent_growth_rate=Decimal("0.02"),
    lease_expiration_month=5,
    turnover_cost_per_unit_or_bed=Decimal("1500.00"),
    annual_turnover_rate=Decimal("0.5"),
    purchase_price=Decimal("32000000.00"),
    closing_costs=Decimal("640000.00"),
    loan_amount=Decimal("20800000.00"),
    interest_rate=Decimal("0.0615"),
    amortization_years=30,
    hold_period_years=10,
    exit_cap_rate=Decimal("0.05"),
    selling_costs_rate=Decimal("0.02"),
)

ALL_SEED_DEALS = [STUDENT_HOUSING, SUBURBAN_GARDEN, URBAN_MIDRISE]

"""See docs/build-plan.md 1.1 — DealInputs rejects a per-bed deal carrying
unit fields, and vice versa, mirroring the nullable column pairs in
app/models/deal.py.
"""

from decimal import Decimal

import pytest

from app.engine.types import DealInputs, LeasingMode, SubAssetClass

COMMON_KWARGS = dict(
    name="Validation Test Deal",
    sub_asset_class=SubAssetClass.SUBURBAN_GARDEN,
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


def test_per_bed_deal_rejects_unit_fields():
    with pytest.raises(ValueError):
        DealInputs(
            leasing_mode=LeasingMode.PER_BED,
            bed_count=100,
            monthly_rent_per_bed=Decimal("800.00"),
            unit_count=100,  # should not be populated for per-bed
            monthly_rent_per_unit=None,
            **COMMON_KWARGS,
        )


def test_per_unit_deal_rejects_bed_fields():
    with pytest.raises(ValueError):
        DealInputs(
            leasing_mode=LeasingMode.PER_UNIT,
            unit_count=100,
            monthly_rent_per_unit=Decimal("1000.00"),
            bed_count=100,  # should not be populated for per-unit
            monthly_rent_per_bed=None,
            **COMMON_KWARGS,
        )


def test_per_bed_deal_requires_bed_fields():
    with pytest.raises(ValueError):
        DealInputs(
            leasing_mode=LeasingMode.PER_BED,
            bed_count=None,
            monthly_rent_per_bed=None,
            unit_count=None,
            monthly_rent_per_unit=None,
            **COMMON_KWARGS,
        )


def test_valid_per_unit_deal_constructs():
    deal = DealInputs(
        leasing_mode=LeasingMode.PER_UNIT,
        unit_count=100,
        monthly_rent_per_unit=Decimal("1000.00"),
        bed_count=None,
        monthly_rent_per_bed=None,
        **COMMON_KWARGS,
    )
    assert deal.unit_or_bed_count == 100


def test_valid_per_bed_deal_constructs():
    deal = DealInputs(
        leasing_mode=LeasingMode.PER_BED,
        bed_count=200,
        monthly_rent_per_bed=Decimal("700.00"),
        unit_count=None,
        monthly_rent_per_unit=None,
        **COMMON_KWARGS,
    )
    assert deal.unit_or_bed_count == 200

"""Load one canned example deal per sub-type (student housing, suburban
garden, urban mid-rise) so the whole team is testing the comparison table
against the same numbers without hand-typing deals.

Usage (with DATABASE_URL set, e.g. via docker-compose up + .env):
    python seed.py
"""
import os
import uuid
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Deal, LeasingMode, SubAssetClass

SEED_DEALS = [
    Deal(
        id=uuid.uuid4(),
        name="Campus View Student Housing",
        sub_asset_class=SubAssetClass.STUDENT_HOUSING,
        leasing_mode=LeasingMode.PER_BED,
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
    ),
    Deal(
        id=uuid.uuid4(),
        name="Willowbrook Suburban Garden",
        sub_asset_class=SubAssetClass.SUBURBAN_GARDEN,
        leasing_mode=LeasingMode.PER_UNIT,
        unit_count=180,
        monthly_rent_per_unit=Decimal("1450.00"),
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
    ),
    Deal(
        id=uuid.uuid4(),
        name="Meridian Urban Mid-Rise",
        sub_asset_class=SubAssetClass.URBAN_MIDRISE,
        leasing_mode=LeasingMode.PER_UNIT,
        unit_count=95,
        monthly_rent_per_unit=Decimal("2100.00"),
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
    ),
]


def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_engine(database_url)
    with Session(engine) as session:
        session.add_all(SEED_DEALS)
        session.commit()
    print(f"Seeded {len(SEED_DEALS)} deals.")


if __name__ == "__main__":
    main()

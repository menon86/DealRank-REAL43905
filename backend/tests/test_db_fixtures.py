"""See docs/build-plan.md 0.3 accept criterion: two tests writing the same
deal name both pass, in either order — proving db_session's per-test
rollback actually isolates tests. Needs Postgres (DATABASE_URL); see
docker-compose.yml.
"""

from decimal import Decimal

from app.models import Deal, LeasingMode, SubAssetClass


def _make_deal() -> Deal:
    return Deal(
        name="Duplicate Name Test Deal",
        sub_asset_class=SubAssetClass.SUBURBAN_GARDEN,
        leasing_mode=LeasingMode.PER_UNIT,
        unit_count=10,
        monthly_rent_per_unit=Decimal("1000.00"),
        vacancy_rate=Decimal("0.05"),
        other_income_annual=Decimal("0"),
        opex_annual=Decimal("50000.00"),
        expense_growth_rate=Decimal("0.03"),
        rent_growth_rate=Decimal("0.03"),
        turnover_cost_per_unit_or_bed=Decimal("500.00"),
        annual_turnover_rate=Decimal("0.5"),
        purchase_price=Decimal("1000000.00"),
        closing_costs=Decimal("20000.00"),
        loan_amount=Decimal("650000.00"),
        interest_rate=Decimal("0.06"),
        amortization_years=30,
        hold_period_years=10,
        exit_cap_rate=Decimal("0.06"),
        selling_costs_rate=Decimal("0.02"),
    )


def test_write_deal_a(db_session):
    db_session.add(_make_deal())
    db_session.flush()


def test_write_deal_b(db_session):
    """Same deal name as test_write_deal_a. Passes regardless of test
    order because db_session rolls back after every test.
    """
    db_session.add(_make_deal())
    db_session.flush()

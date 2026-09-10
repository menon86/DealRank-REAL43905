"""Golden-case tests. See docs/build-plan.md 2.1 and
docs/golden-case-derivation.md for the hand derivation these assert
against — the derivation is computed independently of app/engine, not by
reading the engine's own output.
"""

from decimal import Decimal

import pytest

from app.engine.debt import amortization_schedule
from app.engine.metrics import compute
from app.engine.waterfall import project
from tests.engine.fixtures import ALL_SEED_DEALS, STUDENT_HOUSING, SUBURBAN_GARDEN, URBAN_MIDRISE
from tests.engine.independent_math import (
    closed_form_balance,
    make_amortizing_deal,
)

CENT = Decimal("0.01")


def approx_equal(a: Decimal, b: Decimal, tolerance: Decimal = CENT) -> bool:
    return abs(a - b) <= tolerance


@pytest.mark.parametrize(
    "deal,expected_gpr,expected_vacancy_loss,expected_egi,expected_turnover,expected_noi",
    [
        (
            STUDENT_HOUSING,
            Decimal("2160000.00"),
            Decimal("129600.00"),
            Decimal("2066400.00"),
            Decimal("71400.00"),
            Decimal("1375000.00"),
        ),
        (
            SUBURBAN_GARDEN,
            Decimal("3132000.00"),
            Decimal("156600.00"),
            Decimal("3029400.00"),
            Decimal("89100.00"),
            Decimal("1960300.00"),
        ),
        (
            URBAN_MIDRISE,
            Decimal("2394000.00"),
            Decimal("167580.00"),
            Decimal("2268420.00"),
            Decimal("71250.00"),
            Decimal("1327170.00"),
        ),
    ],
    ids=["student_housing", "suburban_garden", "urban_midrise"],
)
def test_year_one_matches_hand_derivation(
    deal, expected_gpr, expected_vacancy_loss, expected_egi, expected_turnover, expected_noi
):
    result = project(deal)
    year_one = result.annual_cash_flows[0]

    assert approx_equal(year_one.gpr, expected_gpr)
    assert approx_equal(year_one.vacancy_loss, expected_vacancy_loss)
    assert approx_equal(year_one.egi, expected_egi)
    assert approx_equal(year_one.turnover_expense, expected_turnover)
    assert approx_equal(year_one.noi, expected_noi)


@pytest.mark.parametrize(
    "deal,expected_cap_rate",
    [
        (STUDENT_HOUSING, Decimal("1375000.00") / Decimal("21500000.00")),
        (SUBURBAN_GARDEN, Decimal("1960300.00") / Decimal("28800000.00")),
        (URBAN_MIDRISE, Decimal("1327170.00") / Decimal("32000000.00")),
    ],
    ids=["student_housing", "suburban_garden", "urban_midrise"],
)
def test_going_in_cap_rate_matches_hand_derivation(deal, expected_cap_rate):
    metrics = compute(deal)
    assert approx_equal(metrics.going_in_cap_rate, expected_cap_rate, tolerance=Decimal("0.0001"))


@pytest.mark.parametrize(
    "deal",
    ALL_SEED_DEALS,
    ids=["student_housing", "suburban_garden", "urban_midrise"],
)
def test_debt_schedule_matches_closed_form(deal):
    """Cross-checks app/engine/debt.py's simulated ending balance against
    the standard closed-form remaining-balance formula, computed
    independently in tests/engine/independent_math.py rather than by
    calling into app/engine.
    """
    schedule = amortization_schedule(deal)

    year_one_expected = closed_form_balance(
        deal.loan_amount, deal.interest_rate, deal.amortization_years, months=12
    )
    assert approx_equal(schedule[0].ending_balance, year_one_expected, tolerance=Decimal("0.05"))

    hold_expected = closed_form_balance(
        deal.loan_amount,
        deal.interest_rate,
        deal.amortization_years,
        months=deal.hold_period_years * 12,
    )
    assert approx_equal(schedule[-1].ending_balance, hold_expected, tolerance=Decimal("0.05"))


def test_full_amortization_ends_at_zero_balance():
    """1.4 accept criterion: a loan held for exactly its amortization
    period ends with a zero balance, within a cent.
    """
    deal = make_amortizing_deal(hold_period_years=30, amortization_years=30)
    schedule = amortization_schedule(deal)
    assert approx_equal(schedule[-1].ending_balance, Decimal("0"))


@pytest.mark.parametrize(
    "deal",
    ALL_SEED_DEALS,
    ids=["student_housing", "suburban_garden", "urban_midrise"],
)
def test_full_annual_table_reconciles(deal):
    """Every year's line items reconcile against each other, per the full
    table matching a spreadsheet to the cent (1.5 accept criterion).
    """
    result = project(deal)
    for cf in result.annual_cash_flows:
        assert approx_equal(cf.egi, cf.gpr - cf.vacancy_loss + cf.other_income)
        assert approx_equal(cf.noi, cf.egi - cf.opex - cf.turnover_expense)
        assert approx_equal(cf.debt_service, cf.interest_paid + cf.principal_paid)
        assert approx_equal(cf.levered_cash_flow, cf.noi - cf.debt_service)
        assert approx_equal(cf.unlevered_cash_flow, cf.noi)


@pytest.mark.parametrize(
    "deal",
    ALL_SEED_DEALS,
    ids=["student_housing", "suburban_garden", "urban_midrise"],
)
def test_exit_value_uses_forward_noi(deal):
    """Decision D1: exit value is year N+1 NOI over the exit cap rate, not
    year N NOI. Recomputed independently by growing year-1 NOI's inputs
    one more year past the hold, rather than reading waterfall.py.
    """
    from tests.engine.independent_math import forward_noi

    result = project(deal)
    expected_forward_noi = forward_noi(deal, deal.hold_period_years + 1)
    expected_exit_value = expected_forward_noi / deal.exit_cap_rate

    assert approx_equal(result.exit_value, expected_exit_value, tolerance=Decimal("1.00"))


@pytest.mark.parametrize(
    "deal",
    [STUDENT_HOUSING, SUBURBAN_GARDEN],
    ids=["student_housing", "suburban_garden"],
)
def test_irr_direction_is_positively_levered(deal):
    """1.6 accept criterion: the two IRRs differ in the expected direction
    for a positively-levered seeded deal — levered IRR above unlevered.
    Student housing and suburban garden both borrow at a rate below their
    going-in cap rate (positive leverage), so this holds for them.
    """
    metrics = compute(deal)
    assert metrics.unlevered_irr is not None
    assert metrics.levered_irr is not None
    assert metrics.levered_irr > metrics.unlevered_irr


def test_irr_direction_is_negatively_levered_for_urban_midrise():
    """Meridian Urban Mid-Rise borrows at 6.15% against a 4.15% going-in
    cap rate — negative leverage by construction of the seed data — so
    its levered IRR is correctly *below* its unlevered IRR. This is a
    property of the seed deal, not an engine bug; documented here so it
    isn't mistaken for one later.
    """
    metrics = compute(URBAN_MIDRISE)
    assert metrics.unlevered_irr is not None
    assert metrics.levered_irr is not None
    assert metrics.levered_irr < metrics.unlevered_irr

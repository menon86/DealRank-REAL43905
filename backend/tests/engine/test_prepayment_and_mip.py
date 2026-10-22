"""Prepayment penalties at the sale and FHA mortgage insurance on HUD loans.
Each case checks the engine against an independent calculation written out
here, on a golden-case fixture with one financing change.
"""

from dataclasses import replace
from decimal import Decimal

import pytest

from app.engine.debt import monthly_payment, prepayment_penalty
from app.engine.financing import validate_capital_stack
from app.engine.metrics import compute
from app.engine.types import FinancingLayer, LayerType, PrepaymentType
from tests.engine.fixtures import SUBURBAN_GARDEN

CENT = Decimal("0.01")
SPONSOR = FinancingLayer(layer_type=LayerType.SPONSOR_GP, amount=Decimal("0"))
AMOUNT = Decimal("18000000")


def _loan(layer_type=LayerType.AGENCY_FANNIE_MAE, **overrides) -> FinancingLayer:
    fields = dict(
        layer_type=layer_type,
        amount=AMOUNT,
        interest_rate=Decimal("0.06"),
        amortization_years=30,
        term_years=10,
    )
    fields.update(overrides)
    return FinancingLayer(**fields)


def _deal(*layers, hold=10):
    return replace(
        SUBURBAN_GARDEN, hold_period_years=hold, capital_stack=tuple(layers) + (SPONSOR,)
    )


def _balances(amount: Decimal, rate: Decimal, years: int, months: int) -> list[Decimal]:
    """Opening balance of each month of a level-payment loan."""
    payment = monthly_payment(amount, rate, years)
    balance, opening = amount, []
    for _ in range(months):
        opening.append(balance)
        balance -= payment - balance * rate / 12
    return opening


# ------------------------------------------------------------ HUD insurance


def test_hud_mortgage_insurance_is_in_debt_service_and_dscr():
    mip = Decimal("0.0025")
    plain = compute(_deal(_loan(LayerType.HUD_223F)))
    insured = compute(_deal(_loan(LayerType.HUD_223F, mip_annual_rate=mip, mip_upfront_rate=mip)))

    expected_y1 = sum(b * mip / 12 for b in _balances(AMOUNT, Decimal("0.06"), 30, 12))
    y1, y1_plain = insured.annual_cash_flows[0], plain.annual_cash_flows[0]
    assert abs(y1.mortgage_insurance - expected_y1) < CENT
    assert y1.debt_service == y1_plain.debt_service + y1.mortgage_insurance
    assert insured.year_one_dscr == y1.noi / y1.debt_service
    assert insured.year_one_dscr < plain.year_one_dscr

    # Upfront premium is paid at closing out of equity.
    assert insured.equity_invested == plain.equity_invested + AMOUNT * mip
    assert insured.unlevered_irr == plain.unlevered_irr


# -------------------------------------------------------------- step-down


@pytest.mark.parametrize("hold, rate", [(3, "0.03"), (5, "0.01"), (8, "0")])
def test_step_down_charges_the_loan_year_rate_on_the_exit_balance(hold, rate):
    schedule = tuple(Decimal(r) for r in ("0.05", "0.04", "0.03", "0.02", "0.01"))
    bank = _loan(
        LayerType.BANK_CREDIT_UNION,
        prepayment_type=PrepaymentType.STEP_DOWN,
        prepayment_schedule=schedule,
    )
    plain = compute(_deal(_loan(LayerType.BANK_CREDIT_UNION), hold=hold))
    metrics = compute(_deal(bank, hold=hold))

    assert metrics.prepayment_penalties == plain.loan_balance_at_exit * Decimal(rate)
    assert metrics.net_sale_proceeds == plain.net_sale_proceeds - metrics.prepayment_penalties
    assert metrics.unlevered_irr == plain.unlevered_irr


# ------------------------------------------------- yield maintenance / defeasance

# Interest-only loans keep the balance flat, so the expected values below
# are plain annuity sums: 7-year hold, 10-year term = 36 months remaining.
TREASURY = Decimal("0.04")
REMAINING = 36


def _discount(i: int) -> Decimal:
    return (1 + TREASURY / 12) ** i


def test_yield_maintenance_is_the_present_value_of_lost_interest():
    loan = _loan(
        amortization_years=None,
        prepayment_type=PrepaymentType.YIELD_MAINTENANCE,
        prepayment_treasury_rate=TREASURY,
    )
    expected = sum(
        AMOUNT * (Decimal("0.06") - TREASURY) / 12 / _discount(i) for i in range(1, REMAINING + 1)
    )
    assert abs(prepayment_penalty(loan, 7) - expected) < CENT
    assert abs(compute(_deal(loan, hold=7)).prepayment_penalties - expected) < CENT


def test_yield_maintenance_has_a_one_percent_floor():
    loan = _loan(
        amortization_years=None,
        prepayment_type=PrepaymentType.YIELD_MAINTENANCE,
        prepayment_treasury_rate=Decimal("0.065"),  # above the note rate
    )
    assert prepayment_penalty(loan, 7) == AMOUNT * Decimal("0.01")


def test_defeasance_is_the_treasury_portfolio_cost_above_the_balance():
    loan = _loan(
        LayerType.CMBS,
        amortization_years=None,
        prepayment_type=PrepaymentType.DEFEASANCE,
        prepayment_treasury_rate=TREASURY,
    )
    replacement = sum(AMOUNT * Decimal("0.06") / 12 / _discount(i) for i in range(1, REMAINING + 1))
    replacement += AMOUNT / _discount(REMAINING)
    assert abs(prepayment_penalty(loan, 7) - (replacement - AMOUNT)) < CENT


def test_defeasance_is_free_when_treasuries_yield_more_than_the_note():
    loan = _loan(
        LayerType.CMBS,
        amortization_years=None,
        prepayment_type=PrepaymentType.DEFEASANCE,
        prepayment_treasury_rate=Decimal("0.07"),
    )
    assert prepayment_penalty(loan, 7) == 0


@pytest.mark.parametrize(
    "prepayment",
    [PrepaymentType.YIELD_MAINTENANCE, PrepaymentType.DEFEASANCE],
)
def test_no_penalty_when_the_loan_matures_by_the_exit(prepayment):
    loan = _loan(prepayment_type=prepayment, prepayment_treasury_rate=TREASURY, term_years=7)
    assert prepayment_penalty(loan, 7) == 0
    assert prepayment_penalty(loan, 10) == 0  # matured (balloon) in year 7


# --------------------------------------------------------------- validation


@pytest.mark.parametrize(
    "layer, message",
    [
        (_loan(mip_annual_rate=Decimal("0.0025")), "mortgage insurance applies only"),
        (_loan(prepayment_type=PrepaymentType.STEP_DOWN), "needs a schedule"),
        (
            _loan(prepayment_type=PrepaymentType.YIELD_MAINTENANCE, term_years=None),
            "need a term",
        ),
        (_loan(prepayment_type=PrepaymentType.DEFEASANCE), "need a Treasury rate"),
        (
            _loan(
                prepayment_type=PrepaymentType.STEP_DOWN,
                prepayment_schedule=(Decimal("1.5"),),
            ),
            "between 0 and 100%",
        ),
    ],
)
def test_invalid_prepayment_and_insurance_inputs(layer, message):
    errors = validate_capital_stack([layer, SPONSOR])
    assert any(message in error for error in errors), errors


def test_prepayment_only_on_debt_and_insurance_allowed_on_assumed_loans():
    equity = replace(SPONSOR, prepayment_type=PrepaymentType.STEP_DOWN)
    errors = validate_capital_stack([_loan(), equity])
    assert any("only debt layers" in error for error in errors)

    assumed = _loan(LayerType.LOAN_ASSUMPTION, mip_annual_rate=Decimal("0.0045"))
    assert validate_capital_stack([assumed, SPONSOR]) == []

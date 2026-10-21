"""Loan amortization. See docs/build-plan.md 1.4 (decision D2 in section
2) — each loan amortizes monthly, and monthly interest/principal are
aggregated up to an annual figure. Compounding annually instead would
overstate principal paydown.

Each debt layer of the capital stack (app/engine/financing.py) gets its
own schedule: fixed or floating (index + spread, held flat — no forward
curve), an optional interest-only period, then level amortization over
the remaining amortization period (amortization years − I/O months, per
TASK.md section 4), and an optional maturity. A loan maturing inside the
hold is repaid as a balloon that month; no refinancing is modeled.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.engine.financing import MONTHS_PER_YEAR, debt_layers
from app.engine.types import DealInputs, FinancingLayer, LayerGroup


@dataclass(frozen=True)
class AnnualDebtService:
    year: int
    interest_paid: Decimal
    principal_paid: Decimal
    debt_service: Decimal
    ending_balance: Decimal
    balloon_payment: Decimal = Decimal("0")


def _level_payment(principal: Decimal, annual_interest_rate: Decimal, n_payments: int) -> Decimal:
    if principal == 0:
        return Decimal("0")

    monthly_rate = annual_interest_rate / MONTHS_PER_YEAR

    if monthly_rate == 0:
        return principal / n_payments

    factor = (1 + monthly_rate) ** n_payments
    return principal * monthly_rate * factor / (factor - 1)


def monthly_payment(
    loan_amount: Decimal, annual_interest_rate: Decimal, amortization_years: int
) -> Decimal:
    """Level monthly payment for a fully-amortizing loan. Zero for a
    zero-balance loan rather than raising.
    """
    return _level_payment(loan_amount, annual_interest_rate, amortization_years * MONTHS_PER_YEAR)


def layer_schedule(layer: FinancingLayer, hold_period_years: int) -> list[AnnualDebtService]:
    """Annual debt service, interest/principal split, balloon and ending
    balance for one debt layer, for each year of the hold, built by
    simulating the monthly schedule and aggregating.
    """
    annual_rate = layer.all_in_rate
    monthly_rate = annual_rate / MONTHS_PER_YEAR
    maturity_month = layer.term_years * MONTHS_PER_YEAR if layer.term_years is not None else None
    if maturity_month is not None and maturity_month >= hold_period_years * MONTHS_PER_YEAR:
        # Matures at (or after) the exit: the sale repays it, so it's in
        # the exit's loan payoff, not a balloon out of operating cash flow.
        maturity_month = None

    schedule: list[AnnualDebtService] = []
    balance = layer.amount
    payment: Decimal | None = None

    for year in range(1, hold_period_years + 1):
        year_interest = Decimal("0")
        year_principal = Decimal("0")
        year_balloon = Decimal("0")

        for month_of_year in range(1, MONTHS_PER_YEAR + 1):
            if balance <= 0:
                break
            month = (year - 1) * MONTHS_PER_YEAR + month_of_year
            interest = balance * monthly_rate

            amortizing = layer.amortization_years is not None and month > layer.io_months
            if amortizing:
                if payment is None:
                    # Solved once, on the balance at the end of I/O, over
                    # the months of amortization left after it.
                    remaining = layer.amortization_years * MONTHS_PER_YEAR - layer.io_months
                    payment = _level_payment(balance, annual_rate, remaining)
                principal = payment - interest
                if principal > balance:
                    # Final payment: don't overpay past a zero balance.
                    principal = balance
            else:
                principal = Decimal("0")

            balance -= principal
            year_interest += interest
            year_principal += principal

            if month == maturity_month and balance > 0:
                year_balloon += balance
                balance = Decimal("0")

        schedule.append(
            AnnualDebtService(
                year=year,
                interest_paid=year_interest,
                principal_paid=year_principal,
                debt_service=year_interest + year_principal,
                ending_balance=balance,
                balloon_payment=year_balloon,
            )
        )

    return schedule


@dataclass(frozen=True)
class StackDebtYear:
    """One year of debt across every layer: the combined totals, plus the
    senior loan's share (for senior DSCR)."""

    combined: AnnualDebtService
    senior_debt_service: Decimal


def stack_schedule(deal: DealInputs) -> list[StackDebtYear]:
    """Every debt layer's schedule, summed year by year. A deal with no
    debt produces hold_period_years rows of zeros.
    """
    per_layer = [
        (layer, layer_schedule(layer, deal.hold_period_years)) for layer in debt_layers(deal)
    ]

    years: list[StackDebtYear] = []
    for index in range(deal.hold_period_years):
        rows = [schedule[index] for _, schedule in per_layer]
        senior = sum(
            (
                schedule[index].debt_service
                for layer, schedule in per_layer
                if layer.group is LayerGroup.SENIOR
            ),
            Decimal("0"),
        )
        years.append(
            StackDebtYear(
                combined=AnnualDebtService(
                    year=index + 1,
                    interest_paid=sum((r.interest_paid for r in rows), Decimal("0")),
                    principal_paid=sum((r.principal_paid for r in rows), Decimal("0")),
                    debt_service=sum((r.debt_service for r in rows), Decimal("0")),
                    ending_balance=sum((r.ending_balance for r in rows), Decimal("0")),
                    balloon_payment=sum((r.balloon_payment for r in rows), Decimal("0")),
                ),
                senior_debt_service=senior,
            )
        )
    return years


def amortization_schedule(deal: DealInputs) -> list[AnnualDebtService]:
    """Combined annual debt service across every debt layer (for a deal
    without a capital stack, the single loan's schedule) for each year
    of deal.hold_period_years. loan_amount = 0 produces hold_period_years
    rows of all zeros rather than dividing by zero.
    """
    return [year.combined for year in stack_schedule(deal)]

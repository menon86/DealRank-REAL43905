"""Fixed-rate amortization. See docs/build-plan.md 1.4 (decision D2 in
section 2) — the loan amortizes monthly, and monthly interest/principal
are aggregated up to an annual figure. Compounding annually instead would
overstate principal paydown.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.engine.types import DealInputs

MONTHS_PER_YEAR = 12


@dataclass(frozen=True)
class AnnualDebtService:
    year: int
    interest_paid: Decimal
    principal_paid: Decimal
    debt_service: Decimal
    ending_balance: Decimal


def monthly_payment(
    loan_amount: Decimal, annual_interest_rate: Decimal, amortization_years: int
) -> Decimal:
    """Level monthly payment for a fully-amortizing loan. Zero for a
    zero-balance loan rather than raising.
    """
    if loan_amount == 0:
        return Decimal("0")

    n_payments = amortization_years * MONTHS_PER_YEAR
    monthly_rate = annual_interest_rate / MONTHS_PER_YEAR

    if monthly_rate == 0:
        return loan_amount / n_payments

    factor = (1 + monthly_rate) ** n_payments
    return loan_amount * monthly_rate * factor / (factor - 1)


def amortization_schedule(deal: DealInputs) -> list[AnnualDebtService]:
    """Annual debt service, interest/principal split, and ending balance
    for each year of deal.hold_period_years, built by simulating the
    underlying monthly schedule and aggregating. loan_amount = 0 produces
    hold_period_years rows of all zeros rather than dividing by zero.
    """
    payment = monthly_payment(deal.loan_amount, deal.interest_rate, deal.amortization_years)
    monthly_rate = deal.interest_rate / MONTHS_PER_YEAR

    schedule: list[AnnualDebtService] = []
    balance = deal.loan_amount

    for year in range(1, deal.hold_period_years + 1):
        year_interest = Decimal("0")
        year_principal = Decimal("0")

        for _ in range(MONTHS_PER_YEAR):
            if balance <= 0:
                break
            interest = balance * monthly_rate
            principal = payment - interest
            if principal > balance:
                # Final payment: don't overpay past a zero balance.
                principal = balance
                this_payment = principal + interest
            else:
                this_payment = payment
            balance -= principal
            year_interest += interest
            year_principal += principal
            _ = this_payment  # per-month payment isn't reported separately

        schedule.append(
            AnnualDebtService(
                year=year,
                interest_paid=year_interest,
                principal_paid=year_principal,
                debt_service=year_interest + year_principal,
                ending_balance=balance,
            )
        )

    return schedule

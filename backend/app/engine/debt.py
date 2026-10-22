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

HUD loans add the FHA mortgage insurance premium (annual rate on the
outstanding balance, paid monthly) to debt service. A loan repaid at the
sale before it matures pays its prepayment penalty — step-down, yield
maintenance or defeasance — out of the sale proceeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.engine.financing import MONTHS_PER_YEAR, debt_layers
from app.engine.types import DealInputs, FinancingLayer, LayerGroup, PrepaymentType


@dataclass(frozen=True)
class AnnualDebtService:
    year: int
    interest_paid: Decimal
    principal_paid: Decimal
    debt_service: Decimal
    ending_balance: Decimal
    balloon_payment: Decimal = Decimal("0")
    # FHA mortgage insurance; included in debt_service.
    mortgage_insurance: Decimal = Decimal("0")


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


@dataclass(frozen=True)
class _Month:
    interest: Decimal
    principal: Decimal
    mortgage_insurance: Decimal
    balloon: Decimal
    opening_balance: Decimal
    ending_balance: Decimal


def _simulate(layer: FinancingLayer, months: int, maturity_month: int | None) -> list[_Month]:
    """The layer month by month: interest-only, then level amortization;
    FHA mortgage insurance on the opening balance; and, at maturity_month,
    the remaining balance repaid as a balloon.
    """
    annual_rate = layer.all_in_rate
    monthly_rate = annual_rate / MONTHS_PER_YEAR
    monthly_mip = layer.mip_annual_rate / MONTHS_PER_YEAR

    rows: list[_Month] = []
    balance = layer.amount
    payment: Decimal | None = None

    for month in range(1, months + 1):
        if balance <= 0:
            zero = Decimal("0")
            rows.append(_Month(zero, zero, zero, zero, zero, zero))
            continue
        opening = balance
        interest = balance * monthly_rate
        mip = balance * monthly_mip

        amortizing = layer.amortization_years is not None and month > layer.io_months
        if amortizing:
            if payment is None:
                # Solved once, on the balance at the end of I/O, over the
                # months of amortization left after it.
                remaining = layer.amortization_years * MONTHS_PER_YEAR - layer.io_months
                payment = _level_payment(balance, annual_rate, remaining)
            principal = payment - interest
            if principal > balance:
                # Final payment: don't overpay past a zero balance.
                principal = balance
        else:
            principal = Decimal("0")

        balance -= principal
        balloon = Decimal("0")
        if month == maturity_month and balance > 0:
            balloon = balance
            balance = Decimal("0")
        rows.append(_Month(interest, principal, mip, balloon, opening, balance))

    return rows


def _maturity_month(layer: FinancingLayer) -> int | None:
    return layer.term_years * MONTHS_PER_YEAR if layer.term_years is not None else None


def layer_schedule(layer: FinancingLayer, hold_period_years: int) -> list[AnnualDebtService]:
    """Annual debt service (interest + principal + mortgage insurance),
    balloon and ending balance for one debt layer, for each year of the
    hold, built by simulating the monthly schedule and aggregating.
    """
    hold_months = hold_period_years * MONTHS_PER_YEAR
    maturity_month = _maturity_month(layer)
    if maturity_month is not None and maturity_month >= hold_months:
        # Matures at (or after) the exit: the sale repays it, so it's in
        # the exit's loan payoff, not a balloon out of operating cash flow.
        maturity_month = None
    rows = _simulate(layer, hold_months, maturity_month)

    schedule: list[AnnualDebtService] = []
    for year in range(1, hold_period_years + 1):
        months = rows[(year - 1) * MONTHS_PER_YEAR : year * MONTHS_PER_YEAR]
        interest = sum((m.interest for m in months), Decimal("0"))
        principal = sum((m.principal for m in months), Decimal("0"))
        mip = sum((m.mortgage_insurance for m in months), Decimal("0"))
        schedule.append(
            AnnualDebtService(
                year=year,
                interest_paid=interest,
                principal_paid=principal,
                debt_service=interest + principal + mip,
                ending_balance=months[-1].ending_balance,
                balloon_payment=sum((m.balloon for m in months), Decimal("0")),
                mortgage_insurance=mip,
            )
        )

    return schedule


# Yield maintenance is never less than this share of the balance prepaid.
YIELD_MAINTENANCE_FLOOR = Decimal("0.01")


def prepayment_penalty(layer: FinancingLayer, hold_period_years: int) -> Decimal:
    """What repaying this layer at the sale (end of the hold) costs, on top
    of its balance. Zero for a loan already repaid or matured, and for
    yield maintenance / defeasance once the exit is at or past maturity.
    """
    if not layer.is_debt or layer.prepayment_type is PrepaymentType.NONE:
        return Decimal("0")

    exit_month = hold_period_years * MONTHS_PER_YEAR
    maturity_month = _maturity_month(layer)
    if maturity_month is not None and maturity_month <= exit_month:
        return Decimal("0")

    if layer.prepayment_type is PrepaymentType.STEP_DOWN:
        balance = _simulate(layer, exit_month, None)[-1].ending_balance
        # The sale closes in the last month of loan year N (= the hold).
        schedule = layer.prepayment_schedule
        rate = schedule[hold_period_years - 1] if hold_period_years <= len(schedule) else 0
        return balance * Decimal(rate)

    # Yield maintenance and defeasance price the payments the lender would
    # have received from the exit to maturity, discounted at Treasury.
    rows = _simulate(layer, maturity_month, maturity_month)
    balance = rows[exit_month - 1].ending_balance
    if balance <= 0:
        return Decimal("0")
    treasury = layer.prepayment_treasury_rate or Decimal("0")
    monthly_treasury = treasury / MONTHS_PER_YEAR
    remaining = rows[exit_month:]

    def discount(months_out: int) -> Decimal:
        return (1 + monthly_treasury) ** months_out

    if layer.prepayment_type is PrepaymentType.YIELD_MAINTENANCE:
        spread = (layer.all_in_rate - treasury) / MONTHS_PER_YEAR
        lost_interest = sum(
            (m.opening_balance * spread / discount(i) for i, m in enumerate(remaining, start=1)),
            Decimal("0"),
        )
        return max(lost_interest, balance * YIELD_MAINTENANCE_FLOOR)

    # DEFEASANCE: buy Treasuries that pay every remaining payment and the
    # balloon; the cost above the balance retired is the penalty.
    replacement = sum(
        (
            (m.interest + m.principal + m.balloon) / discount(i)
            for i, m in enumerate(remaining, start=1)
        ),
        Decimal("0"),
    )
    return max(replacement - balance, Decimal("0"))


def stack_prepayment_penalties(deal: DealInputs) -> Decimal:
    return sum(
        (prepayment_penalty(layer, deal.hold_period_years) for layer in debt_layers(deal)),
        Decimal("0"),
    )


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
                    mortgage_insurance=sum((r.mortgage_insurance for r in rows), Decimal("0")),
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

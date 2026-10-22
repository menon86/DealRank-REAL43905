"""Year-by-year projection and exit. See docs/build-plan.md 1.5.

Exit value uses forward NOI (decision D1, section 2): year N+1 NOI divided
by the exit cap rate, where N = hold_period_years. Net sale proceeds are
exit value less selling costs less the outstanding balance of every debt
layer at exit and any prepayment penalties, less the return of preferred
equity's capital — debt and preferred equity are paid off ahead of common
equity, in that order.

Levered cash flow is NOI less replacement reserves, debt service (every
debt layer), any balloon repaid inside the hold, and the preferred return
paid to preferred equity. The preferred return is paid only from cash left
after those; any shortfall accrues and is repaid at exit with the capital.
Unlevered cash flow is NOI less reserves, untouched by financing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.engine.debt import stack_prepayment_penalties, stack_schedule
from app.engine.expenses import operating_expenses, turnover_expense
from app.engine.financing import annual_preferred_distribution, total_preferred_equity
from app.engine.revenue import effective_gross_income, gross_potential_rent
from app.engine.types import AnnualCashFlow, DealInputs


@dataclass(frozen=True)
class WaterfallResult:
    annual_cash_flows: list[AnnualCashFlow]
    exit_value: Decimal
    net_sale_proceeds: Decimal
    # The pieces exit value and net sale proceeds are built from, kept so
    # the comparison view can show the exit arithmetic line by line.
    forward_noi: Decimal
    selling_costs: Decimal
    loan_balance_at_exit: Decimal
    preferred_equity_repayment: Decimal = Decimal("0")
    prepayment_penalties: Decimal = Decimal("0")


@dataclass(frozen=True)
class YearOperations:
    gpr: Decimal
    vacancy_loss: Decimal
    credit_loss: Decimal
    other_income: Decimal
    egi: Decimal
    opex: Decimal
    turnover: Decimal
    management_fee: Decimal
    noi: Decimal
    replacement_reserves: Decimal


def _operations_for_year(deal: DealInputs, year: int) -> YearOperations:
    """One year's operating building blocks, shared by the main projection
    and the forward-NOI exit calculation.
    """
    gpr = gross_potential_rent(deal, year)
    other_income = deal.other_income_annual * (1 + deal.other_income_growth_rate) ** (year - 1)
    vacancy_loss, egi = effective_gross_income(gpr, deal.vacancy_rate, other_income)
    credit_loss = gpr * deal.credit_loss_rate
    egi -= credit_loss
    opex = operating_expenses(deal, year)
    turnover = turnover_expense(deal, year)
    management_fee = egi * deal.management_fee_rate
    noi = egi - opex - turnover - management_fee
    reserves = (
        deal.replacement_reserve_per_unit_or_bed
        * deal.unit_or_bed_count
        * (1 + deal.expense_growth_rate) ** (year - 1)
    )
    return YearOperations(
        gpr=gpr,
        vacancy_loss=vacancy_loss,
        credit_loss=credit_loss,
        other_income=other_income,
        egi=egi,
        opex=opex,
        turnover=turnover,
        management_fee=management_fee,
        noi=noi,
        replacement_reserves=reserves,
    )


def project(deal: DealInputs) -> WaterfallResult:
    debt_schedule = stack_schedule(deal)
    preferred_distribution = annual_preferred_distribution(deal)

    annual_cash_flows: list[AnnualCashFlow] = []
    accrued = Decimal("0")
    for year in range(1, deal.hold_period_years + 1):
        ops = _operations_for_year(deal, year)
        gpr, vacancy_loss, egi, opex, turnover, noi = (
            ops.gpr,
            ops.vacancy_loss,
            ops.egi,
            ops.opex,
            ops.turnover,
            ops.noi,
        )

        stack_year = debt_schedule[year - 1]
        debt_year = stack_year.combined
        # Preferred return is paid from what cash flow is left after debt and
        # reserves; any shortfall accrues and is settled at exit.
        available = (
            noi - ops.replacement_reserves - debt_year.debt_service - debt_year.balloon_payment
        )
        paid = min(preferred_distribution, max(available, Decimal("0")))
        shortfall = preferred_distribution - paid
        accrued += shortfall
        levered_cf = available - paid
        unlevered_cf = noi - ops.replacement_reserves

        annual_cash_flows.append(
            AnnualCashFlow(
                year=year,
                gpr=gpr,
                vacancy_loss=vacancy_loss,
                other_income=ops.other_income,
                egi=egi,
                opex=opex,
                turnover_expense=turnover,
                noi=noi,
                debt_service=debt_year.debt_service,
                interest_paid=debt_year.interest_paid,
                principal_paid=debt_year.principal_paid,
                ending_loan_balance=debt_year.ending_balance,
                levered_cash_flow=levered_cf,
                unlevered_cash_flow=unlevered_cf,
                senior_debt_service=stack_year.senior_debt_service,
                balloon_payment=debt_year.balloon_payment,
                mortgage_insurance=debt_year.mortgage_insurance,
                preferred_distribution=paid,
                preferred_shortfall=shortfall,
                preferred_accrued=accrued,
                credit_loss=ops.credit_loss,
                management_fee=ops.management_fee,
                replacement_reserves=ops.replacement_reserves,
            )
        )

    # D1: exit value uses forward (year N+1) NOI over the exit cap rate.
    forward_noi = _operations_for_year(deal, deal.hold_period_years + 1).noi
    # A property with negative forward NOI is worth nothing to a buyer, not
    # a negative amount.
    exit_value = max(forward_noi / deal.exit_cap_rate, Decimal("0"))

    ending_balance = debt_schedule[-1].combined.ending_balance if debt_schedule else Decimal("0")
    preferred_repayment = total_preferred_equity(deal) + accrued
    selling_costs = exit_value * deal.selling_costs_rate
    # Loans repaid at the sale before maturity pay their prepayment penalty
    # (step-down, yield maintenance or defeasance) out of the proceeds.
    prepayment_penalties = stack_prepayment_penalties(deal)
    net_sale_proceeds = (
        exit_value - selling_costs - ending_balance - prepayment_penalties - preferred_repayment
    )

    return WaterfallResult(
        annual_cash_flows=annual_cash_flows,
        exit_value=exit_value,
        net_sale_proceeds=net_sale_proceeds,
        forward_noi=forward_noi,
        selling_costs=selling_costs,
        loan_balance_at_exit=ending_balance,
        preferred_equity_repayment=preferred_repayment,
        prepayment_penalties=prepayment_penalties,
    )

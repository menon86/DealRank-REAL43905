"""Year-by-year projection and exit. See docs/build-plan.md 1.5.

Exit value uses forward NOI (decision D1, section 2): year N+1 NOI divided
by the exit cap rate, where N = hold_period_years. Net sale proceeds are
exit value less selling costs less the outstanding loan balance at exit.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.engine.debt import amortization_schedule
from app.engine.expenses import operating_expenses, turnover_expense
from app.engine.revenue import effective_gross_income, gross_potential_rent
from app.engine.types import AnnualCashFlow, DealInputs


@dataclass(frozen=True)
class WaterfallResult:
    annual_cash_flows: list[AnnualCashFlow]
    exit_value: Decimal
    net_sale_proceeds: Decimal


def _noi_for_year(
    deal: DealInputs, year: int
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    """Returns (gpr, vacancy_loss, egi, opex, turnover, noi) building blocks
    for one year, shared by the main projection and the forward-NOI exit
    calculation.
    """
    gpr = gross_potential_rent(deal, year)
    vacancy_loss, egi = effective_gross_income(gpr, deal.vacancy_rate, deal.other_income_annual)
    opex = operating_expenses(deal, year)
    turnover = turnover_expense(deal, year)
    noi = egi - opex - turnover
    return gpr, vacancy_loss, egi, opex, turnover, noi


def project(deal: DealInputs) -> WaterfallResult:
    debt_schedule = amortization_schedule(deal)

    annual_cash_flows: list[AnnualCashFlow] = []
    for year in range(1, deal.hold_period_years + 1):
        gpr, vacancy_loss, egi, opex, turnover, noi = _noi_for_year(deal, year)

        debt_year = debt_schedule[year - 1]
        levered_cf = noi - debt_year.debt_service
        unlevered_cf = noi

        annual_cash_flows.append(
            AnnualCashFlow(
                year=year,
                gpr=gpr,
                vacancy_loss=vacancy_loss,
                other_income=deal.other_income_annual,
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
            )
        )

    # D1: exit value uses forward (year N+1) NOI over the exit cap rate.
    _, _, _, _, _, forward_noi = _noi_for_year(deal, deal.hold_period_years + 1)
    exit_value = forward_noi / deal.exit_cap_rate

    ending_balance = debt_schedule[-1].ending_balance if debt_schedule else Decimal("0")
    selling_costs = exit_value * deal.selling_costs_rate
    net_sale_proceeds = exit_value - selling_costs - ending_balance

    return WaterfallResult(
        annual_cash_flows=annual_cash_flows,
        exit_value=exit_value,
        net_sale_proceeds=net_sale_proceeds,
    )

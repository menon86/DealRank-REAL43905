"""Independent reference implementations used only by tests, to cross-check
app/engine without re-testing the engine against itself. Nothing here
imports app.engine.debt, app.engine.revenue, or app.engine.expenses.
"""

from decimal import Decimal

from app.engine.types import DealInputs, LeasingMode, SubAssetClass

MONTHS_PER_YEAR = 12


def closed_form_balance(
    loan_amount: Decimal, annual_rate: Decimal, amortization_years: int, months: int
) -> Decimal:
    """Standard closed-form remaining balance of a level-payment
    amortizing loan after `months` payments:

        r = annual_rate / 12
        n = amortization_years x 12
        M = P x r x (1+r)^n / ((1+r)^n - 1)
        B_k = P x (1+r)^k - M x ((1+r)^k - 1) / r
    """
    if loan_amount == 0:
        return Decimal("0")

    r = annual_rate / MONTHS_PER_YEAR
    n = amortization_years * MONTHS_PER_YEAR

    if r == 0:
        m = loan_amount / n
        return loan_amount - m * months

    factor_n = (1 + r) ** n
    payment = loan_amount * r * factor_n / (factor_n - 1)

    factor_k = (1 + r) ** months
    balance = loan_amount * factor_k - payment * (factor_k - 1) / r
    return max(balance, Decimal("0"))


def forward_noi(deal: DealInputs, year: int) -> Decimal:
    """Independently recomputes NOI for an arbitrary year (including
    year hold_period_years + 1, used for the D1 forward-NOI exit
    calculation) directly from Decimal arithmetic, not by calling
    app.engine.revenue / app.engine.expenses.
    """
    if deal.leasing_mode is LeasingMode.PER_UNIT:
        count = Decimal(deal.unit_count)
        monthly_rate = deal.monthly_rent_per_unit
    else:
        count = Decimal(deal.bed_count)
        monthly_rate = deal.monthly_rent_per_bed

    year_one_gpr = count * monthly_rate * MONTHS_PER_YEAR
    gpr = year_one_gpr * (1 + deal.rent_growth_rate) ** (year - 1)
    vacancy_loss = gpr * deal.vacancy_rate
    egi = gpr - vacancy_loss + deal.other_income_annual

    growth = (1 + deal.expense_growth_rate) ** (year - 1)
    opex = deal.opex_annual * growth
    turnover = deal.turnover_cost_per_unit_or_bed * count * deal.annual_turnover_rate * growth

    return egi - opex - turnover


def make_amortizing_deal(hold_period_years: int, amortization_years: int) -> DealInputs:
    """A synthetic deal for debt-schedule edge cases, independent of the
    seed deals in seed.py, so debt tests don't couple to their exact
    figures.
    """
    return DealInputs(
        name="Synthetic Test Deal",
        sub_asset_class=SubAssetClass.SUBURBAN_GARDEN,
        leasing_mode=LeasingMode.PER_UNIT,
        unit_count=100,
        monthly_rent_per_unit=Decimal("1000.00"),
        bed_count=None,
        monthly_rent_per_bed=None,
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
        amortization_years=amortization_years,
        hold_period_years=hold_period_years,
        exit_cap_rate=Decimal("0.06"),
        selling_costs_rate=Decimal("0.02"),
    )

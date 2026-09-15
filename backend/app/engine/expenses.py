"""OpEx growth and the turnover line. See docs/build-plan.md 1.3.

Per D3 (docs/build-plan.md), lease_expiration_month does not shift timing
in this annual model — turnover is charged evenly across the year, every
year, not concentrated around the expiration month. The field is carried
on DealInputs for display and for Deliverable 3's monthly model only;
nothing in this module reads it.
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.types import DealInputs


def operating_expenses(deal: DealInputs, year: int) -> Decimal:
    """Year-1 OpEx grown at expense_growth_rate for `year` (1-indexed).
    Excludes turnover, which is reported as its own line by
    turnover_expense() rather than folded in here.
    """
    growth_factor = (1 + deal.expense_growth_rate) ** (year - 1)
    return deal.opex_annual * growth_factor


def turnover_expense(deal: DealInputs, year: int) -> Decimal:
    """turnover_cost_per_unit_or_bed x (units or beds) x annual_turnover_rate,
    grown at the same expense_growth_rate as the rest of OpEx, reported
    separately rather than folded into total OpEx.
    """
    year_one_turnover = (
        deal.turnover_cost_per_unit_or_bed * deal.unit_or_bed_count * deal.annual_turnover_rate
    )
    growth_factor = (1 + deal.expense_growth_rate) ** (year - 1)
    return year_one_turnover * growth_factor

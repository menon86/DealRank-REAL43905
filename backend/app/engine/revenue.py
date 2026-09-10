"""GPR and EGI. See docs/build-plan.md 1.2 — per-unit and per-bed inputs
converge on one EGI function; there are not two parallel EGI paths.
"""

from __future__ import annotations

from decimal import Decimal

from app.engine.types import DealInputs, LeasingMode

MONTHS_PER_YEAR = 12


def gross_potential_rent(deal: DealInputs, year: int) -> Decimal:
    """Year-1 GPR grown at rent_growth_rate for `year` (1-indexed).

    Per-unit GPR is units x monthly_rent x 12. Per-bed GPR is
    beds x monthly_rent_per_bed x 12. Both are "count x monthly rate x 12",
    which is why this is one function rather than a branch per mode beyond
    picking the count/rate pair.
    """
    if deal.leasing_mode is LeasingMode.PER_UNIT:
        count = Decimal(deal.unit_count)
        monthly_rate = deal.monthly_rent_per_unit
    else:
        count = Decimal(deal.bed_count)
        monthly_rate = deal.monthly_rent_per_bed

    year_one_gpr = count * monthly_rate * MONTHS_PER_YEAR
    growth_factor = (1 + deal.rent_growth_rate) ** (year - 1)
    return year_one_gpr * growth_factor


def effective_gross_income(
    gpr: Decimal, vacancy_rate: Decimal, other_income_annual: Decimal
) -> tuple[Decimal, Decimal]:
    """Resolves any GPR (per-unit or per-bed, already grown for the year)
    into EGI. Returns (vacancy_loss, egi) so callers can report vacancy
    loss as its own line.

    EGI = GPR - vacancy loss + other income
    """
    vacancy_loss = gpr * vacancy_rate
    egi = gpr - vacancy_loss + other_income_annual
    return vacancy_loss, egi

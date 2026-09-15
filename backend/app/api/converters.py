"""ORM row -> engine input conversion. See docs/build-plan.md 3.1 and
1.1 — this converter is what keeps app/engine free of any SQLAlchemy
import: the engine only ever sees the plain DealInputs dataclass built
here.
"""

from fastapi import HTTPException

from app.engine.types import DealInputs
from app.engine.types import LeasingMode as EngineLeasingMode
from app.engine.types import SubAssetClass as EngineSubAssetClass
from app.models.deal import Deal


def deal_to_engine_inputs(deal: Deal) -> DealInputs:
    """Converts a persisted Deal row into the engine's DealInputs. Raises
    HTTPException(422) if the row's leasing-mode/branch pairing is
    inconsistent — this shouldn't happen given the schema-level
    validation on create/update, but a row could in principle be edited
    directly in the DB, and the engine's own DealInputs.__post_init__
    would otherwise raise a bare ValueError that FastAPI turns into a
    500, not a 422.
    """
    try:
        return DealInputs(
            name=deal.name,
            sub_asset_class=EngineSubAssetClass(deal.sub_asset_class.value),
            leasing_mode=EngineLeasingMode(deal.leasing_mode.value),
            unit_count=deal.unit_count,
            monthly_rent_per_unit=deal.monthly_rent_per_unit,
            bed_count=deal.bed_count,
            monthly_rent_per_bed=deal.monthly_rent_per_bed,
            vacancy_rate=deal.vacancy_rate,
            other_income_annual=deal.other_income_annual,
            opex_annual=deal.opex_annual,
            expense_growth_rate=deal.expense_growth_rate,
            rent_growth_rate=deal.rent_growth_rate,
            lease_expiration_month=deal.lease_expiration_month,
            turnover_cost_per_unit_or_bed=deal.turnover_cost_per_unit_or_bed,
            annual_turnover_rate=deal.annual_turnover_rate,
            purchase_price=deal.purchase_price,
            closing_costs=deal.closing_costs,
            loan_amount=deal.loan_amount,
            interest_rate=deal.interest_rate,
            amortization_years=deal.amortization_years,
            hold_period_years=deal.hold_period_years,
            exit_cap_rate=deal.exit_cap_rate,
            selling_costs_rate=deal.selling_costs_rate,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Deal {deal.id} has an inconsistent leasing_mode/branch pairing: {exc}",
        ) from exc

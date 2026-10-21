"""ORM row -> engine input conversion. See docs/build-plan.md 3.1 and
1.1 — this converter is what keeps app/engine free of any SQLAlchemy
import: the engine only ever sees the plain DealInputs dataclass built
here.
"""

from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.engine.types import DealInputs, FinancingLayer, LayerType, RateType
from app.engine.types import LeasingMode as EngineLeasingMode
from app.engine.types import SubAssetClass as EngineSubAssetClass
from app.models.deal import Deal


def _decimal(value: Any) -> Decimal | None:
    # JSON-stored layers carry decimals as strings ("0.0625"); str() first
    # so a float never becomes a binary-fraction Decimal.
    return None if value is None else Decimal(str(value))


def engine_layer(data: dict[str, Any]) -> FinancingLayer:
    """One capital stack layer, as stored in deals.capital_stack (or as
    dumped from the API schema), to the engine's FinancingLayer.
    """
    return FinancingLayer(
        layer_type=LayerType(data["type"]),
        amount=_decimal(data["amount"]),
        label=data.get("label"),
        rate_type=RateType(data.get("rate_type") or RateType.FIXED),
        interest_rate=_decimal(data.get("interest_rate")),
        index_name=data.get("index_name"),
        index_rate=_decimal(data.get("index_rate")),
        spread=_decimal(data.get("spread")),
        io_months=data.get("io_months") or 0,
        amortization_years=data.get("amortization_years"),
        term_years=data.get("term_years"),
        recourse=data.get("recourse"),
        rate_cap_cost=_decimal(data.get("rate_cap_cost")) or Decimal("0"),
        origination_fee_rate=_decimal(data.get("origination_fee_rate")) or Decimal("0"),
        preferred_return=_decimal(data.get("preferred_return")),
    )


def deal_to_engine_inputs(deal: Deal) -> DealInputs:
    """Converts a persisted Deal row into the engine's DealInputs. Raises
    HTTPException(422) if the row's leasing-mode/branch pairing or its
    capital stack is inconsistent — this shouldn't happen given the
    schema-level validation on create/update, but a row could in
    principle be edited directly in the DB, and the engine's own
    DealInputs.__post_init__ would otherwise raise a bare ValueError that
    FastAPI turns into a 500, not a 422.
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
            capital_stack=tuple(engine_layer(layer) for layer in deal.capital_stack or []),
            other_income_growth_rate=deal.other_income_growth_rate,
            credit_loss_rate=deal.credit_loss_rate,
            management_fee_rate=deal.management_fee_rate,
            replacement_reserve_per_unit_or_bed=deal.replacement_reserve_per_unit_or_bed,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Deal {deal.id} has inconsistent inputs: {exc}",
        ) from exc

"""Request/response schemas. See docs/build-plan.md 3.1 and the frozen
API contract in section 5. Money is a decimal string over the wire, rates
are decimal fractions — pydantic v2 serializes Decimal as a JSON string by
default, which gives us both for free without a float ever entering the
wire format.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.deal import LeasingMode, SubAssetClass


class DealBase(BaseModel):
    name: str
    sub_asset_class: SubAssetClass
    leasing_mode: LeasingMode

    unit_count: int | None = None
    monthly_rent_per_unit: Decimal | None = None
    bed_count: int | None = None
    monthly_rent_per_bed: Decimal | None = None

    vacancy_rate: Decimal
    other_income_annual: Decimal = Decimal("0")

    opex_annual: Decimal
    expense_growth_rate: Decimal
    rent_growth_rate: Decimal

    lease_expiration_month: int = 8
    turnover_cost_per_unit_or_bed: Decimal
    annual_turnover_rate: Decimal

    purchase_price: Decimal
    closing_costs: Decimal
    loan_amount: Decimal
    interest_rate: Decimal
    amortization_years: int

    hold_period_years: int
    exit_cap_rate: Decimal
    selling_costs_rate: Decimal

    @model_validator(mode="after")
    def _leasing_mode_matches_populated_branch(self) -> "DealBase":
        """Mirrors app/engine/types.py's DealInputs validation: exactly
        one of the per-unit / per-bed branches populated, matching
        leasing_mode. Raised as a plain ValueError so FastAPI turns it
        into a 422 naming the offending field.
        """
        if self.leasing_mode is LeasingMode.PER_UNIT:
            if self.unit_count is None or self.monthly_rent_per_unit is None:
                raise ValueError(
                    "leasing_mode is per_unit but unit_count and/or "
                    "monthly_rent_per_unit is missing"
                )
            if self.bed_count is not None or self.monthly_rent_per_bed is not None:
                raise ValueError(
                    "leasing_mode is per_unit but bed_count and/or "
                    "monthly_rent_per_bed is also populated"
                )
        else:
            if self.bed_count is None or self.monthly_rent_per_bed is None:
                raise ValueError(
                    "leasing_mode is per_bed but bed_count and/or "
                    "monthly_rent_per_bed is missing"
                )
            if self.unit_count is not None or self.monthly_rent_per_unit is not None:
                raise ValueError(
                    "leasing_mode is per_bed but unit_count and/or "
                    "monthly_rent_per_unit is also populated"
                )
        return self


class DealCreate(DealBase):
    pass


class DealUpdate(BaseModel):
    """All fields optional — PATCH semantics. Cross-field leasing-mode
    validation only runs on the fully-resolved row in the converter
    (app/api/converters.py), since a partial update may only touch one
    field of a pair.
    """

    name: str | None = None
    sub_asset_class: SubAssetClass | None = None
    leasing_mode: LeasingMode | None = None

    unit_count: int | None = None
    monthly_rent_per_unit: Decimal | None = None
    bed_count: int | None = None
    monthly_rent_per_bed: Decimal | None = None

    vacancy_rate: Decimal | None = None
    other_income_annual: Decimal | None = None

    opex_annual: Decimal | None = None
    expense_growth_rate: Decimal | None = None
    rent_growth_rate: Decimal | None = None

    lease_expiration_month: int | None = None
    turnover_cost_per_unit_or_bed: Decimal | None = None
    annual_turnover_rate: Decimal | None = None

    purchase_price: Decimal | None = None
    closing_costs: Decimal | None = None
    loan_amount: Decimal | None = None
    interest_rate: Decimal | None = None
    amortization_years: int | None = None

    hold_period_years: int | None = None
    exit_cap_rate: Decimal | None = None
    selling_costs_rate: Decimal | None = None


class DealOut(DealBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AnnualCashFlowOut(BaseModel):
    # from_attributes: app/engine returns plain dataclasses
    # (AnnualCashFlow, DealMetrics), not dicts — FastAPI's response_model
    # validation needs this to read them by attribute.
    model_config = ConfigDict(from_attributes=True)

    year: int
    gpr: Decimal
    vacancy_loss: Decimal
    other_income: Decimal
    egi: Decimal
    opex: Decimal
    turnover_expense: Decimal
    noi: Decimal
    debt_service: Decimal
    interest_paid: Decimal
    principal_paid: Decimal
    ending_loan_balance: Decimal
    levered_cash_flow: Decimal
    unlevered_cash_flow: Decimal


class MetricsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    annual_cash_flows: list[AnnualCashFlowOut]
    year_one_noi: Decimal
    going_in_cap_rate: Decimal
    year_one_dscr: Decimal | None
    cash_on_cash: Decimal | None
    unlevered_irr: Decimal | None
    levered_irr: Decimal | None
    equity_multiple: Decimal | None
    exit_value: Decimal
    net_sale_proceeds: Decimal


class RankRequest(BaseModel):
    deal_ids: list[uuid.UUID]
    hurdle_rate: Decimal


RANKING_BASIS_NOTE = (
    "Ranked by unlevered IRR minus the supplied hurdle rate, descending. "
    "Levered IRR is included for reference only and is never sorted on."
)


class RankedDealOut(BaseModel):
    deal: DealOut
    metrics: MetricsOut
    spread: Decimal
    rank: int
    # 3.4 accept criterion: the response carries an explicit basis note,
    # so an exported report can't be read as ranking on levered returns.
    # Section 5's frozen contract types this endpoint's response as
    # RankedDealOut[] (a bare array), so the note travels on every
    # element rather than in an envelope around the array.
    basis_note: str = RANKING_BASIS_NOTE

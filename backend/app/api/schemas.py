"""Request/response schemas. See docs/build-plan.md 3.1 and the frozen
API contract in section 5. Money is a decimal string over the wire, rates
are decimal fractions — pydantic v2 serializes Decimal as a JSON string by
default, which gives us both for free without a float ever entering the
wire format.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.ranking_data import RANKING_BASIS_NOTE
from app.models.deal import LeasingMode, SubAssetClass


class DealBase(BaseModel):
    name: str
    sub_asset_class: SubAssetClass
    leasing_mode: LeasingMode

    unit_count: int | None = Field(default=None, gt=0)
    monthly_rent_per_unit: Decimal | None = Field(default=None, ge=0)
    bed_count: int | None = Field(default=None, gt=0)
    monthly_rent_per_bed: Decimal | None = Field(default=None, ge=0)

    vacancy_rate: Decimal = Field(ge=0, le=1)
    other_income_annual: Decimal = Field(default=Decimal("0"), ge=0)

    opex_annual: Decimal = Field(ge=0)
    expense_growth_rate: Decimal = Field(gt=-1, le=1)
    rent_growth_rate: Decimal = Field(gt=-1, le=1)

    lease_expiration_month: int = Field(default=8, ge=1, le=12)
    turnover_cost_per_unit_or_bed: Decimal = Field(ge=0)
    annual_turnover_rate: Decimal = Field(ge=0, le=1)

    purchase_price: Decimal = Field(gt=0)
    closing_costs: Decimal = Field(ge=0)
    loan_amount: Decimal = Field(ge=0)
    interest_rate: Decimal = Field(ge=0, le=1)
    amortization_years: int = Field(gt=0, le=50)

    hold_period_years: int = Field(gt=0, le=30)
    exit_cap_rate: Decimal = Field(gt=0, le=1)
    selling_costs_rate: Decimal = Field(ge=0, lt=1)

    @model_validator(mode="after")
    def _leasing_mode_matches_populated_branch(self) -> "DealBase":
        """Mirrors app/engine/types.py's DealInputs validation: exactly
        one of the per-unit / per-bed branches populated, matching
        leasing_mode. Raised as a plain ValueError so FastAPI turns it
        into a 422 naming the offending field.
        """
        if self.loan_amount > self.purchase_price:
            raise ValueError("loan_amount cannot exceed purchase_price")
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
    equity_invested: Decimal
    total_distributions: Decimal
    forward_noi: Decimal
    selling_costs: Decimal
    loan_balance_at_exit: Decimal


class RankRequest(BaseModel):
    deal_ids: list[uuid.UUID] = Field(min_length=1)
    hurdle_rate: Decimal


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

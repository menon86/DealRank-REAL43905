"""Request/response schemas. See docs/build-plan.md 3.1 and the frozen
API contract in section 5. Money is a decimal string over the wire, rates
are decimal fractions — pydantic v2 serializes Decimal as a JSON string by
default, which gives us both for free without a float ever entering the
wire format.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.api.converters import engine_layer
from app.api.ranking_data import RANKING_BASIS_NOTE
from app.engine.financing import common_equity_errors, validate_capital_stack
from app.engine.types import FinancingLayer, LayerGroup, LayerType, PrepaymentType, RateType
from app.models.deal import LeasingMode, SubAssetClass

DealName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
LayerLabel = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
IndexName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]


class CapitalStackLayer(BaseModel):
    """One capital stack layer. Which fields matter depends on the type:
    debt layers use the rate/term fields, preferred equity uses
    preferred_return, equity layers only amount and label. The cross-layer
    rules (one senior loan, at least one equity layer, ...) live in
    app/engine/financing.py validate_capital_stack.
    """

    type: LayerType
    label: LayerLabel | None = None
    amount: Decimal = Field(ge=0)

    rate_type: RateType = RateType.FIXED
    interest_rate: Decimal | None = Field(default=None, ge=0, le=1)
    index_name: IndexName | None = None
    index_rate: Decimal | None = Field(default=None, ge=0, le=1)
    spread: Decimal | None = Field(default=None, ge=0, le=1)
    io_months: int = Field(default=0, ge=0, le=600)
    amortization_years: int | None = Field(default=None, gt=0, le=50)
    term_years: int | None = Field(default=None, gt=0, le=50)
    recourse: bool | None = None

    rate_cap_cost: Decimal = Field(default=Decimal("0"), ge=0)
    origination_fee_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)

    preferred_return: Decimal | None = Field(default=None, ge=0, le=1)

    prepayment_type: PrepaymentType = PrepaymentType.NONE
    # Step-down: share of the balance by loan year, year 1 first.
    prepayment_schedule: list[Annotated[Decimal, Field(ge=0, le=1)]] = Field(
        default_factory=list, max_length=50
    )
    prepayment_treasury_rate: Decimal | None = Field(default=None, ge=0, le=1)

    # FHA mortgage insurance (HUD loans).
    mip_annual_rate: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("0.05"))
    mip_upfront_rate: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("0.05"))


class UnitMixTier(BaseModel):
    id: Annotated[str, StringConstraints(max_length=50)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
    units: int = Field(ge=0)
    beds_per_unit: int = Field(ge=1, le=20)
    avg_sqft: int = Field(ge=0)
    rent: Decimal = Field(ge=0)


class DealBase(BaseModel):
    name: DealName
    sub_asset_class: SubAssetClass
    leasing_mode: LeasingMode

    unit_count: int | None = Field(default=None, gt=0)
    monthly_rent_per_unit: Decimal | None = Field(default=None, gt=0)
    bed_count: int | None = Field(default=None, gt=0)
    monthly_rent_per_bed: Decimal | None = Field(default=None, gt=0)

    vacancy_rate: Decimal = Field(ge=0, le=1)
    other_income_annual: Decimal = Field(default=Decimal("0"), ge=0)

    opex_annual: Decimal = Field(ge=0)
    # Expenses don't shrink; rent growth may be negative (a declining market).
    expense_growth_rate: Decimal = Field(ge=0, le=1)
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

    # None = the single loan above. When set, loan_amount / interest_rate /
    # amortization_years are overwritten from the senior layer (see
    # _capital_stack_rules), so they always describe the senior loan.
    capital_stack: list[CapitalStackLayer] | None = Field(default=None, max_length=20)

    # Optional lines; 0 reproduces the original model.
    other_income_growth_rate: Decimal = Field(default=Decimal("0"), gt=-1, le=1)
    credit_loss_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    management_fee_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    replacement_reserve_per_unit_or_bed: Decimal = Field(default=Decimal("0"), ge=0)

    # The unit mix the aggregate unit/bed count and rent were built from.
    # Descriptive only: the engine runs on the aggregates.
    unit_mix: list[UnitMixTier] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _capital_stack_rules(self) -> "DealBase":
        """Checks the stack against validate_capital_stack, then mirrors the
        senior layer onto the single-loan fields. An all-cash stack sets the
        loan amount and rate to zero (amortization keeps whatever was sent,
        since the column can't be zero and a zero loan never reads it).
        """
        if not self.capital_stack:
            return self
        layers = [engine_layer(layer.model_dump()) for layer in self.capital_stack]
        errors = validate_capital_stack(layers)
        if not errors:
            errors = common_equity_errors(self.purchase_price, self.closing_costs, layers)
        if errors:
            raise ValueError("capital_stack: " + " ".join(errors))

        senior = next((layer for layer in layers if layer.group is LayerGroup.SENIOR), None)
        if senior is None:
            self.loan_amount = Decimal("0")
            self.interest_rate = Decimal("0")
        else:
            self.loan_amount = senior.amount
            self.interest_rate = senior.all_in_rate
            if senior.amortization_years is not None:
                self.amortization_years = senior.amortization_years
        return self

    @model_validator(mode="after")
    def _leasing_mode_matches_populated_branch(self) -> "DealBase":
        """Mirrors app/engine/types.py's DealInputs validation: exactly
        one of the per-unit / per-bed branches populated, matching
        leasing_mode. Raised as a plain ValueError so FastAPI turns it
        into a 422 naming the offending field.
        """
        if self.loan_amount > self.purchase_price:
            raise ValueError("loan_amount cannot exceed purchase_price")
        if not self.capital_stack:
            errors = common_equity_errors(
                self.purchase_price,
                self.closing_costs,
                [
                    FinancingLayer(
                        layer_type=LayerType.OTHER_SENIOR,
                        amount=self.loan_amount,
                        interest_rate=self.interest_rate,
                    )
                ],
            )
            if errors:
                raise ValueError(errors[0])
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
    # Explicit null clears the stack and returns the deal to the single loan.
    capital_stack: list[CapitalStackLayer] | None = None
    unit_mix: list[UnitMixTier] | None = None
    other_income_growth_rate: Decimal | None = None
    credit_loss_rate: Decimal | None = None
    management_fee_rate: Decimal | None = None
    replacement_reserve_per_unit_or_bed: Decimal | None = None

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
    senior_debt_service: Decimal
    balloon_payment: Decimal
    preferred_distribution: Decimal
    preferred_shortfall: Decimal
    preferred_accrued: Decimal
    credit_loss: Decimal
    management_fee: Decimal
    replacement_reserves: Decimal
    mortgage_insurance: Decimal


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
    # year_one_dscr is the combined DSCR (every debt layer).
    year_one_senior_dscr: Decimal | None
    total_debt: Decimal
    preferred_equity: Decimal
    upfront_financing_costs: Decimal
    preferred_equity_repayment: Decimal
    prepayment_penalties: Decimal
    unlevered_irr_before_costs: Decimal | None
    min_dscr: Decimal | None
    debt_yield: Decimal | None
    unlevered_cash_yield: Decimal


class RankRequest(BaseModel):
    deal_ids: list[uuid.UUID] = Field(min_length=1, max_length=25)
    hurdle_rate: Decimal = Field(ge=-1, le=1)


class RankedDealOut(BaseModel):
    deal: DealOut
    metrics: MetricsOut
    # None when the deal's unlevered IRR didn't converge (it sorts last).
    spread: Decimal | None
    rank: int
    # 3.4 accept criterion: the response carries an explicit basis note,
    # so an exported report can't be read as ranking on levered returns.
    # Section 5's frozen contract types this endpoint's response as
    # RankedDealOut[] (a bare array), so the note travels on every
    # element rather than in an envelope around the array.
    basis_note: str = RANKING_BASIS_NOTE

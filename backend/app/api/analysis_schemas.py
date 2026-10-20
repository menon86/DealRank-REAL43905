"""Schemas for the Deliverable 3 endpoints: risk-adjusted ranking,
sensitivity, Monte Carlo, and the market-rent sanity check.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.api.schemas import DealOut, MetricsOut
from app.engine.ranking import DEFAULT_DSCR_MINIMUM

PrimaryGoal = Literal["total_return", "cash_flow", "preservation"]


class TreasuryOut(BaseModel):
    yield_: Decimal = Field(serialization_alias="yield")
    as_of: date | None
    source: str


class HurdleOut(BaseModel):
    sub_asset_class: str
    treasury_yield: Decimal
    spread_bps: int
    cap_rate: Decimal  # treasury + spread
    noi_growth: Decimal
    total: Decimal  # the hurdle: cap_rate + noi_growth
    survey_source: str
    survey_quarter: str
    effective_date: date


class HurdleTableOut(BaseModel):
    treasury: TreasuryOut
    hurdles: list[HurdleOut]


class WeightsIn(BaseModel):
    irr: Decimal = Field(ge=0)
    cash_flow: Decimal = Field(ge=0)
    risk: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def _some_positive(self) -> "WeightsIn":
        if self.irr + self.cash_flow + self.risk <= 0:
            raise ValueError("at least one weight must be positive")
        return self


class QuestionnaireIn(BaseModel):
    primary_goal: PrimaryGoal
    risk_tolerance: int = Field(ge=1, le=5)
    income_need: int = Field(ge=1, le=5)


class RiskRankRequest(BaseModel):
    deal_ids: list[uuid.UUID] = Field(min_length=1)
    dscr_minimum: Decimal = Field(default=DEFAULT_DSCR_MINIMUM, ge=0, le=5)
    # Optional manual 10-Year Treasury (decimal fraction); default is live FRED.
    treasury_yield: Decimal | None = Field(default=None, ge=0, le=1)
    # Preferences: explicit weights win over questionnaire answers; with
    # neither, the ranking is purely by spread vs. hurdle.
    weights: WeightsIn | None = None
    answers: QuestionnaireIn | None = None


class WeightsOut(BaseModel):
    irr: Decimal
    cash_flow: Decimal
    risk: Decimal


class FactorScoresOut(BaseModel):
    irr: Decimal
    cash_flow: Decimal
    risk: Decimal


class RiskRankedDealOut(BaseModel):
    rank: int
    deal: DealOut
    metrics: MetricsOut
    hurdle: HurdleOut
    spread: Decimal
    ltv: Decimal
    factors: FactorScoresOut
    score: Decimal


class ExcludedDealOut(BaseModel):
    deal: DealOut
    metrics: MetricsOut
    hurdle: HurdleOut
    reason: str


class RiskRankResponse(BaseModel):
    treasury: TreasuryOut
    dscr_minimum: Decimal
    weights: WeightsOut
    ranked: list[RiskRankedDealOut]
    excluded: list[ExcludedDealOut]
    basis_note: str


# ---------------------------------------------------------------- sensitivity


class SweepRequest(BaseModel):
    variable: Literal["exit_cap_rate", "rent_growth_rate"]
    low: Decimal | None = None  # default: base -/+ a variable-specific span
    high: Decimal | None = None
    steps: int = Field(default=13, ge=2, le=61)


class SweepPointOut(BaseModel):
    value: Decimal
    unlevered_irr: Decimal | None
    levered_irr: Decimal | None
    cash_on_cash: Decimal | None
    equity_multiple: Decimal | None
    min_dscr: Decimal | None
    exit_value: Decimal


class SweepResponse(BaseModel):
    variable: str
    base_value: Decimal
    points: list[SweepPointOut]


class MonteCarloRequest(BaseModel):
    simulations: int = Field(default=1000, ge=1, le=5000)
    seed: int | None = None
    exit_cap_sd: Decimal = Field(default=Decimal("0.005"), ge=0, le=Decimal("0.05"))
    rent_growth_sd: Decimal = Field(default=Decimal("0.01"), ge=0, le=Decimal("0.1"))
    vacancy_sd: Decimal = Field(default=Decimal("0.02"), ge=0, le=Decimal("0.2"))
    hurdle: Decimal | None = None  # default: the deal's risk-adjusted hurdle
    dscr_minimum: Decimal = Field(default=DEFAULT_DSCR_MINIMUM, ge=0, le=5)


class DistributionOut(BaseModel):
    mean: Decimal
    stdev: Decimal
    p5: Decimal
    p25: Decimal
    p50: Decimal
    p75: Decimal
    p95: Decimal


class HistogramBinOut(BaseModel):
    low: Decimal
    high: Decimal
    count: int


class MonteCarloResponse(BaseModel):
    simulations: int
    converged: int
    seed: int | None
    hurdle: Decimal | None
    hurdle_source: str
    unlevered_irr: DistributionOut | None
    levered_irr: DistributionOut | None
    unlevered_histogram: list[HistogramBinOut]
    prob_below_hurdle: Decimal | None
    prob_dscr_below_minimum: Decimal | None


# ---------------------------------------------------------------- rent check


class RentCheckOut(BaseModel):
    status: Literal["ok", "caution", "flag", "not_comparable", "no_data"]
    geography: str
    deal_rent: Decimal | None
    market_rent: Decimal | None
    market_period: date | None
    source: str | None
    variance: Decimal | None
    market_yoy_growth: Decimal | None
    deal_rent_growth: Decimal
    note: str


class RentUploadOut(BaseModel):
    source: str
    inserted: int
    updated: int
    geographies: int


class GeographyOut(BaseModel):
    geography: str
    source: str
    latest_period: date

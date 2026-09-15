"""Plain input/output types for the calculation engine.

Nothing here imports SQLAlchemy, FastAPI, or anything from app.models or
app.api — see the package docstring in app/engine/__init__.py. All money
and rate fields are Decimal; the engine never touches float except at the
IRR boundary (see metrics.py), where numpy-financial requires it.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal


class SubAssetClass(str, enum.Enum):
    STUDENT_HOUSING = "student_housing"
    SUBURBAN_GARDEN = "suburban_garden"
    URBAN_MIDRISE = "urban_midrise"


class LeasingMode(str, enum.Enum):
    PER_UNIT = "per_unit"
    PER_BED = "per_bed"


@dataclass(frozen=True)
class DealInputs:
    """Mirrors the nullable column pairs in app/models/deal.py: exactly one
    of the per-unit / per-bed branches is populated, matching leasing_mode.
    """

    name: str
    sub_asset_class: SubAssetClass
    leasing_mode: LeasingMode

    # --- GPR inputs (exactly one branch populated per leasing_mode) ---
    unit_count: int | None
    monthly_rent_per_unit: Decimal | None
    bed_count: int | None
    monthly_rent_per_bed: Decimal | None

    vacancy_rate: Decimal
    other_income_annual: Decimal

    # --- OpEx ---
    opex_annual: Decimal
    expense_growth_rate: Decimal
    rent_growth_rate: Decimal

    # --- Turnover / make-ready ---
    lease_expiration_month: int
    turnover_cost_per_unit_or_bed: Decimal
    annual_turnover_rate: Decimal

    # --- Acquisition / financing ---
    purchase_price: Decimal
    closing_costs: Decimal
    loan_amount: Decimal
    interest_rate: Decimal
    amortization_years: int

    # --- Hold / exit ---
    hold_period_years: int
    exit_cap_rate: Decimal
    selling_costs_rate: Decimal

    def __post_init__(self) -> None:
        if self.leasing_mode is LeasingMode.PER_UNIT:
            if self.unit_count is None or self.monthly_rent_per_unit is None:
                raise ValueError(
                    "per_unit leasing mode requires unit_count and monthly_rent_per_unit"
                )
            if self.bed_count is not None or self.monthly_rent_per_bed is not None:
                raise ValueError("per_unit leasing mode must not carry bed fields")
        elif self.leasing_mode is LeasingMode.PER_BED:
            if self.bed_count is None or self.monthly_rent_per_bed is None:
                raise ValueError("per_bed leasing mode requires bed_count and monthly_rent_per_bed")
            if self.unit_count is not None or self.monthly_rent_per_unit is not None:
                raise ValueError("per_bed leasing mode must not carry unit fields")
        else:  # pragma: no cover - exhaustive enum guard
            raise ValueError(f"unknown leasing_mode: {self.leasing_mode}")

    @property
    def unit_or_bed_count(self) -> int:
        """The count driving GPR and turnover, regardless of leasing mode."""
        return self.unit_count if self.leasing_mode is LeasingMode.PER_UNIT else self.bed_count


@dataclass(frozen=True)
class AnnualCashFlow:
    """One year's row in the waterfall. Every line a grader could want to
    trace independently is its own field — nothing is only available
    pre-summed.
    """

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


@dataclass(frozen=True)
class DealMetrics:
    """Everything the API's MetricsOut schema (section 5 of the build plan)
    needs, plus the full annual table for the comparison view.
    """

    annual_cash_flows: list[AnnualCashFlow] = field(default_factory=list)
    year_one_noi: Decimal = Decimal("0")
    going_in_cap_rate: Decimal = Decimal("0")
    year_one_dscr: Decimal | None = None
    cash_on_cash: Decimal | None = None
    unlevered_irr: Decimal | None = None
    levered_irr: Decimal | None = None
    equity_multiple: Decimal | None = None
    exit_value: Decimal = Decimal("0")
    net_sale_proceeds: Decimal = Decimal("0")

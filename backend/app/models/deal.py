import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SubAssetClass(str, enum.Enum):
    STUDENT_HOUSING = "student_housing"
    SUBURBAN_GARDEN = "suburban_garden"
    URBAN_MIDRISE = "urban_midrise"


class LeasingMode(str, enum.Enum):
    PER_UNIT = "per_unit"
    PER_BED = "per_bed"


class Deal(Base):
    """User-entered deal inputs. Schema supports both per-unit and per-bed
    records feeding the same downstream calculation engine (see
    app/engine). Do not add engine-derived/calculated fields here — the
    engine recomputes metrics from these inputs on demand rather than
    persisting them, so the DB never holds a stale calculation.
    """

    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_asset_class: Mapped[SubAssetClass] = mapped_column(
        Enum(SubAssetClass, name="sub_asset_class"), nullable=False
    )
    leasing_mode: Mapped[LeasingMode] = mapped_column(
        Enum(LeasingMode, name="leasing_mode"), nullable=False
    )

    # --- GPR inputs (exactly one branch populated per leasing_mode) ---
    unit_count: Mapped[int | None] = mapped_column(nullable=True)
    monthly_rent_per_unit: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)
    bed_count: Mapped[int | None] = mapped_column(nullable=True)
    monthly_rent_per_bed: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)

    vacancy_rate: Mapped[Numeric] = mapped_column(Numeric(6, 4), nullable=False)
    other_income_annual: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    # --- OpEx ---
    opex_annual: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    expense_growth_rate: Mapped[Numeric] = mapped_column(Numeric(6, 4), nullable=False)
    rent_growth_rate: Mapped[Numeric] = mapped_column(Numeric(6, 4), nullable=False)

    # --- Turnover / make-ready (own visible OpEx line; see app/engine) ---
    lease_expiration_month: Mapped[int] = mapped_column(nullable=False, default=8)
    turnover_cost_per_unit_or_bed: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    annual_turnover_rate: Mapped[Numeric] = mapped_column(Numeric(6, 4), nullable=False)

    # --- Acquisition / financing ---
    purchase_price: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    closing_costs: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    loan_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    interest_rate: Mapped[Numeric] = mapped_column(Numeric(6, 4), nullable=False)
    amortization_years: Mapped[int] = mapped_column(nullable=False)

    # --- Hold / exit ---
    hold_period_years: Mapped[int] = mapped_column(nullable=False)
    exit_cap_rate: Mapped[Numeric] = mapped_column(Numeric(6, 4), nullable=False)
    selling_costs_rate: Mapped[Numeric] = mapped_column(Numeric(6, 4), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

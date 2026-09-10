import uuid

from sqlalchemy import Date, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CapRateSpread(Base):
    """Static, versioned cap-rate-to-Treasury spreads by sub-asset class,
    manually seeded from published broker surveys (CBRE/C&W/JLL/Berkadia).
    Not queried live. Stubbed now; consumed by the Deliverable 3
    Treasury+spread hurdle (see app/engine/ranking.py).
    """

    __tablename__ = "cap_rate_spreads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sub_asset_class: Mapped[str] = mapped_column(String(50), nullable=False)
    survey_source: Mapped[str] = mapped_column(String(100), nullable=False)
    survey_quarter: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "2026Q2"
    spread_bps: Mapped[int] = mapped_column(nullable=False)
    assumed_stabilized_noi_growth: Mapped[Numeric] = mapped_column(Numeric(6, 4), nullable=False)
    effective_date: Mapped[Date] = mapped_column(Date, nullable=False)

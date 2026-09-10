import uuid

from sqlalchemy import Date, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MarketRent(Base):
    """Reference rent data from Zillow Research / Apartment List, loaded via
    a periodic CSV ingest job. Stubbed now; not consumed until the
    Deliverable 3 rent sanity-check feature.
    """

    __tablename__ = "market_rents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    geography: Mapped[str] = mapped_column(String(255), nullable=False)
    sub_asset_class: Mapped[str] = mapped_column(String(50), nullable=False)
    period: Mapped[Date] = mapped_column(Date, nullable=False)
    median_rent: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)

"""initial schema: deals, cap_rate_spreads, market_rents

Revision ID: 0001
Revises:
Create Date: 2026-09-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sub_asset_class = postgresql.ENUM(
        "student_housing",
        "suburban_garden",
        "urban_midrise",
        name="sub_asset_class",
    )
    leasing_mode = postgresql.ENUM("per_unit", "per_bed", name="leasing_mode")

    op.create_table(
        "deals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sub_asset_class", sub_asset_class, nullable=False),
        sa.Column("leasing_mode", leasing_mode, nullable=False),
        sa.Column("unit_count", sa.Integer(), nullable=True),
        sa.Column("monthly_rent_per_unit", sa.Numeric(12, 2), nullable=True),
        sa.Column("bed_count", sa.Integer(), nullable=True),
        sa.Column("monthly_rent_per_bed", sa.Numeric(12, 2), nullable=True),
        sa.Column("vacancy_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("other_income_annual", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("opex_annual", sa.Numeric(14, 2), nullable=False),
        sa.Column("expense_growth_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("rent_growth_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("lease_expiration_month", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("turnover_cost_per_unit_or_bed", sa.Numeric(12, 2), nullable=False),
        sa.Column("annual_turnover_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("purchase_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("closing_costs", sa.Numeric(14, 2), nullable=False),
        sa.Column("loan_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("amortization_years", sa.Integer(), nullable=False),
        sa.Column("hold_period_years", sa.Integer(), nullable=False),
        sa.Column("exit_cap_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("selling_costs_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "cap_rate_spreads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sub_asset_class", sa.String(length=50), nullable=False),
        sa.Column("survey_source", sa.String(length=100), nullable=False),
        sa.Column("survey_quarter", sa.String(length=10), nullable=False),
        sa.Column("spread_bps", sa.Integer(), nullable=False),
        sa.Column("assumed_stabilized_noi_growth", sa.Numeric(6, 4), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
    )

    op.create_table(
        "market_rents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("geography", sa.String(length=255), nullable=False),
        sa.Column("sub_asset_class", sa.String(length=50), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("median_rent", sa.Numeric(12, 2), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("market_rents")
    op.drop_table("cap_rate_spreads")
    op.drop_table("deals")
    postgresql.ENUM(name="leasing_mode").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="sub_asset_class").drop(op.get_bind(), checkfirst=True)

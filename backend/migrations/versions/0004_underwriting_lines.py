"""Optional underwriting lines, unit mix, and lookup indexes.

Adds other-income growth, credit loss, management fee and replacement
reserves (all default 0, so existing deals are unchanged), a descriptive
unit_mix JSON column, and indexes on the reference-data lookup columns.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RATE_COLUMNS = ("other_income_growth_rate", "credit_loss_rate", "management_fee_rate")


def upgrade() -> None:
    for column in RATE_COLUMNS:
        op.add_column(
            "deals",
            sa.Column(column, sa.Numeric(8, 6), nullable=False, server_default="0"),
        )
    op.add_column(
        "deals",
        sa.Column(
            "replacement_reserve_per_unit_or_bed",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("deals", sa.Column("unit_mix", postgresql.JSONB(), nullable=True))
    op.create_index("ix_cap_rate_spreads_sub_asset_class", "cap_rate_spreads", ["sub_asset_class"])
    op.create_index("ix_market_rents_geography", "market_rents", ["geography"])


def downgrade() -> None:
    op.drop_index("ix_market_rents_geography", table_name="market_rents")
    op.drop_index("ix_cap_rate_spreads_sub_asset_class", table_name="cap_rate_spreads")
    op.drop_column("deals", "unit_mix")
    op.drop_column("deals", "replacement_reserve_per_unit_or_bed")
    for column in reversed(RATE_COLUMNS):
        op.drop_column("deals", column)

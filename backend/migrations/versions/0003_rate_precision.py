"""Widen rate columns from 4 to 6 decimal places.

Numeric(6,4) silently rounded a 6.125% interest rate to 6.13% and a 5.125%
exit cap to 5.13%; Numeric(8,6) keeps rates to the hundredth of a basis point.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEAL_RATE_COLUMNS = (
    "vacancy_rate",
    "expense_growth_rate",
    "rent_growth_rate",
    "annual_turnover_rate",
    "interest_rate",
    "exit_cap_rate",
    "selling_costs_rate",
)


def _alter(precision: int, scale: int, old_precision: int, old_scale: int) -> None:
    for column in DEAL_RATE_COLUMNS:
        op.alter_column(
            "deals",
            column,
            type_=sa.Numeric(precision, scale),
            existing_type=sa.Numeric(old_precision, old_scale),
            existing_nullable=False,
        )
    op.alter_column(
        "cap_rate_spreads",
        "assumed_stabilized_noi_growth",
        type_=sa.Numeric(precision, scale),
        existing_type=sa.Numeric(old_precision, old_scale),
        existing_nullable=False,
    )


def upgrade() -> None:
    _alter(8, 6, 6, 4)


def downgrade() -> None:
    _alter(6, 4, 8, 6)

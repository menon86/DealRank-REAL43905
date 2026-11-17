"""Add deals.owner_id so each signed-in user sees only their own deals.

Existing rows stay NULL (visible to nobody) until seed.py moves them into the
sample-deal template.

Kept after the sign-in feature was reverted: the deployed database is already at
this revision, so the history must still contain it. The owner_id schema is unused.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-29

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("owner_id", sa.String(320), nullable=True))
    op.create_index("ix_deals_owner_id", "deals", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_deals_owner_id", table_name="deals")
    op.drop_column("deals", "owner_id")

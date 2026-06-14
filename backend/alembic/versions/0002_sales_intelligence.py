"""sales intelligence fields

Revision ID: 0002_sales_intelligence
Revises: 0001_initial_schema
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_sales_intelligence"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use batch_alter_table for SQLite compatibility
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.add_column(sa.Column("lead_stage", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("follow_up_strategy", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("stakeholders", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("risks", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("opportunities", sa.Text(), nullable=True))

    op.create_index(op.f("ix_meetings_lead_stage"), "meetings", ["lead_stage"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_meetings_lead_stage"), table_name="meetings")
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_column("opportunities")
        batch_op.drop_column("risks")
        batch_op.drop_column("stakeholders")
        batch_op.drop_column("follow_up_strategy")
        batch_op.drop_column("lead_stage")

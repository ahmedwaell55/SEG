"""Add meeting fallback audit flag.

Revision ID: 0005_meeting_fallback_flag
Revises: 0004_auth_users
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_meeting_fallback_flag"
down_revision: str | None = "0004_auth_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.add_column(sa.Column("is_fallback", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_index(op.f("ix_meetings_is_fallback"), ["is_fallback"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch_op:
        batch_op.drop_index(op.f("ix_meetings_is_fallback"))
        batch_op.drop_column("is_fallback")

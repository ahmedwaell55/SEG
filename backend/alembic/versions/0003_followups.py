"""add followups

Revision ID: 0003_followups
Revises: 0002_sales_intelligence
Create Date: 2026-05-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_followups"
down_revision: str | None = "0002_sales_intelligence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "followups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("follow_up_number", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("priority_level", sa.String(length=20), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("communication_tone", sa.String(length=80), nullable=True),
        sa.Column("whatsapp_message", sa.Text(), nullable=True),
        sa.Column("transcript_evidence", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_followups_client_id"), "followups", ["client_id"], unique=False)
    op.create_index(op.f("ix_followups_follow_up_number"), "followups", ["follow_up_number"], unique=False)
    op.create_index(op.f("ix_followups_id"), "followups", ["id"], unique=False)
    op.create_index(op.f("ix_followups_meeting_id"), "followups", ["meeting_id"], unique=False)
    op.create_index(op.f("ix_followups_priority_level"), "followups", ["priority_level"], unique=False)
    op.create_index(op.f("ix_followups_scheduled_at"), "followups", ["scheduled_at"], unique=False)
    op.create_index(op.f("ix_followups_status"), "followups", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_followups_status"), table_name="followups")
    op.drop_index(op.f("ix_followups_scheduled_at"), table_name="followups")
    op.drop_index(op.f("ix_followups_priority_level"), table_name="followups")
    op.drop_index(op.f("ix_followups_meeting_id"), table_name="followups")
    op.drop_index(op.f("ix_followups_id"), table_name="followups")
    op.drop_index(op.f("ix_followups_follow_up_number"), table_name="followups")
    op.drop_index(op.f("ix_followups_client_id"), table_name="followups")
    op.drop_table("followups")


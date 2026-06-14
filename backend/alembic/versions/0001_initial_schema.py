"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clients_id"), "clients", ["id"], unique=False)
    op.create_index(op.f("ix_clients_name"), "clients", ["name"], unique=False)
    op.create_index(op.f("ix_clients_phone"), "clients", ["phone"], unique=False)

    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("cleaned_transcript", sa.Text(), nullable=True),
        sa.Column("speaker_notes", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(length=40), nullable=True),
        sa.Column("emotional_tone", sa.String(length=80), nullable=True),
        sa.Column("urgency_level", sa.String(length=40), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("acceptance_probability", sa.Integer(), nullable=True),
        sa.Column("acceptance_label", sa.String(length=20), nullable=True),
        sa.Column("communication_style", sa.Text(), nullable=True),
        sa.Column("sales_strategy", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_meetings_acceptance_label"), "meetings", ["acceptance_label"], unique=False)
    op.create_index(op.f("ix_meetings_acceptance_probability"), "meetings", ["acceptance_probability"], unique=False)
    op.create_index(op.f("ix_meetings_client_id"), "meetings", ["client_id"], unique=False)
    op.create_index(op.f("ix_meetings_id"), "meetings", ["id"], unique=False)
    op.create_index(op.f("ix_meetings_meeting_date"), "meetings", ["meeting_date"], unique=False)
    op.create_index(op.f("ix_meetings_sentiment"), "meetings", ["sentiment"], unique=False)

    for table_name, text_column in (
        ("objections", "objection_text"),
        ("pain_points", "pain_point_text"),
        ("recommendations", "recommendation_text"),
        ("buying_signals", "signal_text"),
        ("next_actions", "action_text"),
    ):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("meeting_id", sa.Integer(), nullable=False),
            sa.Column(text_column, sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f(f"ix_{table_name}_id"), table_name, ["id"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_meeting_id"), table_name, ["meeting_id"], unique=False)


def downgrade() -> None:
    for table_name in ("next_actions", "buying_signals", "recommendations", "pain_points", "objections"):
        op.drop_index(op.f(f"ix_{table_name}_meeting_id"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_id"), table_name=table_name)
        op.drop_table(table_name)

    op.drop_index(op.f("ix_meetings_sentiment"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_meeting_date"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_id"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_client_id"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_acceptance_probability"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_acceptance_label"), table_name="meetings")
    op.drop_table("meetings")

    op.drop_index(op.f("ix_clients_phone"), table_name="clients")
    op.drop_index(op.f("ix_clients_name"), table_name="clients")
    op.drop_index(op.f("ix_clients_id"), table_name="clients")
    op.drop_table("clients")


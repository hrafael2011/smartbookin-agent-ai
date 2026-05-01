"""add processed channel events idempotency table

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-04-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processed_channel_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("user_key", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel",
            "business_id",
            "user_key",
            "event_id",
            name="uq_processed_channel_events_identity",
        ),
    )
    op.create_index(
        op.f("ix_processed_channel_events_channel"),
        "processed_channel_events",
        ["channel"],
        unique=False,
    )
    op.create_index(
        op.f("ix_processed_channel_events_id"),
        "processed_channel_events",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_processed_channel_events_user_key"),
        "processed_channel_events",
        ["user_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_processed_channel_events_user_key"), table_name="processed_channel_events")
    op.drop_index(op.f("ix_processed_channel_events_id"), table_name="processed_channel_events")
    op.drop_index(op.f("ix_processed_channel_events_channel"), table_name="processed_channel_events")
    op.drop_table("processed_channel_events")

"""add owner channel bindings

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "owner_channel_bindings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("channel_user_id", sa.String(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("activation_token", sa.String(length=64), nullable=True),
        sa.Column("activation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel",
            "channel_user_id",
            name="uq_owner_channel_bindings_channel_user",
        ),
    )
    op.create_index(
        op.f("ix_owner_channel_bindings_activation_token"),
        "owner_channel_bindings",
        ["activation_token"],
        unique=True,
    )
    op.create_index(
        op.f("ix_owner_channel_bindings_business_id"),
        "owner_channel_bindings",
        ["business_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_owner_channel_bindings_channel"),
        "owner_channel_bindings",
        ["channel"],
        unique=False,
    )
    op.create_index(
        op.f("ix_owner_channel_bindings_channel_user_id"),
        "owner_channel_bindings",
        ["channel_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_owner_channel_bindings_id"),
        "owner_channel_bindings",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_owner_channel_bindings_owner_id"),
        "owner_channel_bindings",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_owner_channel_bindings_owner_id"), table_name="owner_channel_bindings")
    op.drop_index(op.f("ix_owner_channel_bindings_id"), table_name="owner_channel_bindings")
    op.drop_index(op.f("ix_owner_channel_bindings_channel_user_id"), table_name="owner_channel_bindings")
    op.drop_index(op.f("ix_owner_channel_bindings_channel"), table_name="owner_channel_bindings")
    op.drop_index(op.f("ix_owner_channel_bindings_business_id"), table_name="owner_channel_bindings")
    op.drop_index(op.f("ix_owner_channel_bindings_activation_token"), table_name="owner_channel_bindings")
    op.drop_table("owner_channel_bindings")

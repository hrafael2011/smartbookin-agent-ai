"""telegram multitenant + owner email verification

Revision ID: b1c2d3e4f5a6
Revises: 9f4a6b7c12de
Create Date: 2026-04-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "9f4a6b7c12de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "owners",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("owners", sa.Column("verification_token", sa.String(), nullable=True))
    op.add_column(
        "owners",
        sa.Column("verification_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text("UPDATE owners SET email_verified = true"))
    op.alter_column("owners", "email_verified", server_default=None)

    op.add_column("businesses", sa.Column("telegram_invite_token", sa.String(), nullable=True))
    op.add_column(
        "businesses",
        sa.Column("telegram_first_contact_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_businesses_telegram_invite_token",
        "businesses",
        ["telegram_invite_token"],
        unique=True,
    )

    op.create_table(
        "telegram_user_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_user_id", sa.String(), nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telegram_user_bindings_telegram_user_id",
        "telegram_user_bindings",
        ["telegram_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_user_bindings_telegram_user_id", table_name="telegram_user_bindings")
    op.drop_table("telegram_user_bindings")
    op.drop_index("ix_businesses_telegram_invite_token", table_name="businesses")
    op.drop_column("businesses", "telegram_first_contact_at")
    op.drop_column("businesses", "telegram_invite_token")
    op.drop_column("owners", "verification_token_expires_at")
    op.drop_column("owners", "verification_token")
    op.drop_column("owners", "email_verified")

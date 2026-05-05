"""add buffer minutes to services

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_services_buffer_minutes_nonnegative",
        "services",
        "buffer_minutes >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_services_buffer_minutes_nonnegative",
        "services",
        type_="check",
    )
    op.drop_column("services", "buffer_minutes")

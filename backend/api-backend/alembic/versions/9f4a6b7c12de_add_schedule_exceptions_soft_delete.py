"""add_schedule_exceptions_soft_delete

Revision ID: 9f4a6b7c12de
Revises: e3076e18363c
Create Date: 2026-04-08 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f4a6b7c12de"
down_revision: Union[str, None] = "e3076e18363c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schedule_exceptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("deleted_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"]),
        sa.ForeignKeyConstraint(["deleted_by"], ["owners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_schedule_exceptions_id"), "schedule_exceptions", ["id"], unique=False)
    op.create_index(
        "ix_schedule_exceptions_business_date",
        "schedule_exceptions",
        ["business_id", "date"],
        unique=False,
    )
    op.create_index(
        "ix_schedule_exceptions_deleted_at",
        "schedule_exceptions",
        ["deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_schedule_exceptions_deleted_at", table_name="schedule_exceptions")
    op.drop_index("ix_schedule_exceptions_business_date", table_name="schedule_exceptions")
    op.drop_index(op.f("ix_schedule_exceptions_id"), table_name="schedule_exceptions")
    op.drop_table("schedule_exceptions")

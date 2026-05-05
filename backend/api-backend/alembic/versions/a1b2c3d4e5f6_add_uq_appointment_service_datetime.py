"""add uq_appointment_service_datetime constraint

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-05-05

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_appointment_service_datetime",
        "appointments",
        ["service_id", "date"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_appointment_service_datetime",
        "appointments",
        type_="unique",
    )

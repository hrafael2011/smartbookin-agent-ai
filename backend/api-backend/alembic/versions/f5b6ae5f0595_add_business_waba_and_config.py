"""add business waba and config

Revision ID: f5b6ae5f0595
Revises: b2c3d4e5f6a7
Create Date: 2026-08-30 17:25:45.361281

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5b6ae5f0595'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Registro del tenant WhatsApp: WABA id (Meta) y config per-negocio (plantilla, políticas).
    op.add_column('businesses', sa.Column('waba_id', sa.String(), nullable=True))
    op.create_unique_constraint('uq_businesses_waba_id', 'businesses', ['waba_id'])
    op.add_column('businesses', sa.Column('config_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('businesses', 'config_json')
    op.drop_constraint('uq_businesses_waba_id', 'businesses', type_='unique')
    op.drop_column('businesses', 'waba_id')

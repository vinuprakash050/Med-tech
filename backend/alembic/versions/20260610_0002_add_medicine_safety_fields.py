"""add medicine safety fields

Revision ID: 20260610_0002
Revises: 20260610_0001
Create Date: 2026-06-10 19:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260610_0002"
down_revision: Union[str, Sequence[str], None] = "20260610_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("medicines", sa.Column("common_side_effects", sa.Text(), nullable=True))
    op.add_column("medicines", sa.Column("allergy_warnings", sa.Text(), nullable=True))
    op.add_column("medicines", sa.Column("precautions", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("medicines", "precautions")
    op.drop_column("medicines", "allergy_warnings")
    op.drop_column("medicines", "common_side_effects")


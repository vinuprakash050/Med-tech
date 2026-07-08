"""add openfda medicine fields

Revision ID: 20260611_0003
Revises: 20260610_0002
Create Date: 2026-06-11 10:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260611_0003"
down_revision: Union[str, Sequence[str], None] = "20260610_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("medicines", sa.Column("generic_name", sa.Text(), nullable=True))
    op.add_column("medicines", sa.Column("active_ingredients", sa.Text(), nullable=True))
    op.add_column("medicines", sa.Column("dosage_form", sa.Text(), nullable=True))
    op.add_column("medicines", sa.Column("warnings", sa.Text(), nullable=True))
    op.add_column("medicines", sa.Column("adverse_reactions", sa.Text(), nullable=True))
    op.add_column("medicines", sa.Column("indications", sa.Text(), nullable=True))
    op.add_column("medicines", sa.Column("purpose", sa.Text(), nullable=True))
    op.add_column("medicines", sa.Column("openfda_synced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("medicines", "openfda_synced_at")
    op.drop_column("medicines", "purpose")
    op.drop_column("medicines", "indications")
    op.drop_column("medicines", "adverse_reactions")
    op.drop_column("medicines", "warnings")
    op.drop_column("medicines", "dosage_form")
    op.drop_column("medicines", "active_ingredients")
    op.drop_column("medicines", "generic_name")


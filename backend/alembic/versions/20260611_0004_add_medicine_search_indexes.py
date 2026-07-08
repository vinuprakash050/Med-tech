"""add medicine search indexes

Revision ID: 20260611_0004
Revises: 20260611_0003
Create Date: 2026-06-11 02:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260611_0004"
down_revision = "20260611_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_medicines_lower_name", "medicines", [sa.text("lower(name)")])
    op.create_index(
        "ix_medicines_lower_generic_name",
        "medicines",
        [sa.text("lower(generic_name)")],
    )


def downgrade() -> None:
    op.drop_index("ix_medicines_lower_generic_name", table_name="medicines")
    op.drop_index("ix_medicines_lower_name", table_name="medicines")


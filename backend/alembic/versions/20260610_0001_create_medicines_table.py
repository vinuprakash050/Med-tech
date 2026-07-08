"""create medicines table

Revision ID: 20260610_0001
Revises: 
Create Date: 2026-06-10 18:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260610_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "medicines",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("salt_composition", sa.String(length=255), nullable=False),
        sa.Column("dosage", sa.String(length=50), nullable=False),
        sa.Column("manufacturer", sa.String(length=255), nullable=False),
        sa.Column("medicine_type", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_generic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "approval_status",
            sa.String(length=50),
            nullable=False,
            server_default="approved",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("name", name="uq_medicines_name"),
    )
    op.create_index("ix_medicines_id", "medicines", ["id"], unique=False)
    op.create_index("ix_medicines_name", "medicines", ["name"], unique=False)
    op.create_index(
        "ix_medicines_salt_dosage",
        "medicines",
        ["salt_composition", "dosage"],
        unique=False,
    )
    op.create_index("ix_medicines_is_generic", "medicines", ["is_generic"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_medicines_is_generic", table_name="medicines")
    op.drop_index("ix_medicines_salt_dosage", table_name="medicines")
    op.drop_index("ix_medicines_name", table_name="medicines")
    op.drop_index("ix_medicines_id", table_name="medicines")
    op.drop_table("medicines")

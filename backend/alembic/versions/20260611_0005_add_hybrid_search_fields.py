"""add hybrid search fields (source, fda_cached, last_fda_sync_at, normalized_name)

Revision ID: 20260611_0005
Revises: 20260611_0004
Create Date: 2026-06-11 02:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260611_0005"
down_revision = "20260611_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "medicines",
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="internal",
        ),
    )
    op.add_column(
        "medicines",
        sa.Column(
            "fda_cached",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "medicines",
        sa.Column(
            "last_fda_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "medicines",
        sa.Column(
            "normalized_name",
            sa.String(255),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_medicines_source",
        "medicines",
        ["source"],
    )
    op.create_index(
        "ix_medicines_fda_cached",
        "medicines",
        ["fda_cached"],
    )
    op.create_index(
        "ix_medicines_normalized_name",
        "medicines",
        [sa.text("lower(normalized_name)")],
    )


def downgrade() -> None:
    op.drop_index("ix_medicines_normalized_name", table_name="medicines")
    op.drop_index("ix_medicines_fda_cached", table_name="medicines")
    op.drop_index("ix_medicines_source", table_name="medicines")
    op.drop_column("medicines", "normalized_name")
    op.drop_column("medicines", "last_fda_sync_at")
    op.drop_column("medicines", "fda_cached")
    op.drop_column("medicines", "source")
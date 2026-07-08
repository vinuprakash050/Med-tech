from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Medicine(Base):
    __tablename__ = "medicines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    salt_composition: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str] = mapped_column(String(50), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(255), nullable=False)
    medicine_type: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_generic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_status: Mapped[str] = mapped_column(String(50), nullable=False, default="approved")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    generic_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)
    dosage_form: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    adverse_reactions: Mapped[str | None] = mapped_column(Text, nullable=True)
    indications: Mapped[str | None] = mapped_column(Text, nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    common_side_effects: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergy_warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    precautions: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="internal")
    fda_cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    normalized_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    openfda_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fda_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @property
    def fda_data_available(self) -> bool:
        return any(
            [
                self.generic_name,
                self.active_ingredients,
                self.dosage_form,
                self.warnings,
                self.adverse_reactions,
                self.indications,
                self.purpose,
            ]
        )

    @property
    def display_source(self) -> str:
        if self.fda_cached:
            return "FDA verified generic"
        return self.source

    __table_args__ = (
        Index("ix_medicines_name", "name"),
        Index("ix_medicines_lower_name", func.lower(name)),
        Index("ix_medicines_lower_generic_name", func.lower(generic_name)),
        Index("ix_medicines_salt_dosage", "salt_composition", "dosage"),
        Index("ix_medicines_is_generic", "is_generic"),
        Index("ix_medicines_source", "source"),
        Index("ix_medicines_fda_cached", "fda_cached"),
        Index("ix_medicines_normalized_name", func.lower(normalized_name)),
    )

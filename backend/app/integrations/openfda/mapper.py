from __future__ import annotations

from dataclasses import dataclass, field

from app.integrations.openfda.schemas import OpenFDALabelRecord


def _as_text_list(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    else:
        candidates = value
    return [str(item).strip() for item in candidates if str(item).strip()]


def _join_text(value: list[str] | str | None) -> str | None:
    cleaned = _as_text_list(value)
    if not cleaned:
        return None
    unique_values: list[str] = []
    for item in cleaned:
        if item not in unique_values:
            unique_values.append(item)
    return "\n".join(unique_values)


@dataclass(slots=True)
class OpenFDAMedicineUpdate:
    generic_name: str | None = None
    active_ingredients: str | None = None
    dosage_form: str | None = None
    warnings: str | None = None
    adverse_reactions: str | None = None
    indications: str | None = None
    purpose: str | None = None
    manufacturer_name: str | None = None
    enriched_fields: list[str] = field(default_factory=list)

    def as_db_updates(self) -> dict[str, str | None]:
        return {
            "generic_name": self.generic_name,
            "active_ingredients": self.active_ingredients,
            "dosage_form": self.dosage_form,
            "warnings": self.warnings,
            "adverse_reactions": self.adverse_reactions,
            "indications": self.indications,
            "purpose": self.purpose,
        }


def map_openfda_record(record: OpenFDALabelRecord) -> OpenFDAMedicineUpdate:
    openfda = record.openfda
    update = OpenFDAMedicineUpdate(
        generic_name=(
            str(openfda.generic_name[0]).strip()
            if openfda and openfda.generic_name
            else None
        ),
        active_ingredients=_join_text(record.active_ingredient),
        dosage_form=_join_text(record.dosage_form),
        warnings=_join_text(record.warnings),
        adverse_reactions=_join_text(record.adverse_reactions),
        indications=_join_text(record.indications_and_usage),
        purpose=_join_text(record.purpose),
        manufacturer_name=(
            str(openfda.manufacturer_name[0]).strip()
            if openfda and openfda.manufacturer_name
            else None
        ),
    )

    for field_name in update.as_db_updates():
        if getattr(update, field_name):
            update.enriched_fields.append(field_name)

    return update

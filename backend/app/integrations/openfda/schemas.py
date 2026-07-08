from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OpenFDAPublicFields(BaseModel):
    model_config = ConfigDict(extra="ignore")

    brand_name: list[str] | None = None
    generic_name: list[str] | None = None
    manufacturer_name: list[str] | None = None


class OpenFDALabelRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    openfda: OpenFDAPublicFields | None = None
    active_ingredient: list[str] | str | None = None
    dosage_form: list[str] | str | None = None
    warnings: list[str] | str | None = None
    adverse_reactions: list[str] | str | None = None
    purpose: list[str] | str | None = None
    indications_and_usage: list[str] | str | None = None


class OpenFDALabelResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[OpenFDALabelRecord] = Field(default_factory=list)


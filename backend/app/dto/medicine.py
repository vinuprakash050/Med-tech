from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MedicineInsightsResponse(BaseModel):
    summary: str | None = None
    key_uses: list[str] = Field(default_factory=list)
    important_safety_points: list[str] = Field(default_factory=list)
    who_should_be_careful: list[str] = Field(default_factory=list)
    possible_side_effects: list[str] = Field(default_factory=list)
    pregnancy_breastfeeding: str | None = None
    emergency_warnings: list[str] = Field(default_factory=list)
    why_this_generic: str | None = None


class MedicineSearchRequest(BaseModel):
    medicine_name: str = Field(min_length=1, max_length=255)
    generic_preference: bool = True


class MedicineSuggestionRequest(BaseModel):
    query: str = Field(min_length=1, max_length=255)


class MedicineSuggestionItem(BaseModel):
    medicine_name: str
    confidence: int = Field(ge=1, le=100)
    reason: str


class MedicineSuggestionResponse(BaseModel):
    original_query: str
    suggestions: list[MedicineSuggestionItem]
    fda_fallback_used: bool = False
    fda_search_term: str | None = None


class MedicineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    salt_composition: str
    dosage: str
    manufacturer: str
    medicine_type: str
    price: Decimal
    is_generic: bool
    approval_status: str
    description: str | None = None
    generic_name: str | None = None
    active_ingredients: str | None = None
    dosage_form: str | None = None
    warnings: str | None = None
    adverse_reactions: str | None = None
    indications: str | None = None
    purpose: str | None = None
    common_side_effects: str | None = None
    allergy_warnings: str | None = None
    precautions: str | None = None
    medicine_insights: MedicineInsightsResponse | None = None
    source: str = "internal"
    fda_cached: bool = False
    normalized_name: str | None = None
    openfda_synced_at: datetime | None = None
    last_fda_sync_at: datetime | None = None
    fda_data_available: bool = False
    display_source: str = "internal"
    openfda_requests: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AlternativeMedicineResponse(MedicineResponse):
    price_difference: Decimal
    same_salt: bool = True
    same_dosage: bool = True


class SafetyValidationResponse(BaseModel):
    same_salt: bool
    same_dosage: bool


class RecommendationResponse(BaseModel):
    requested_medicine: MedicineResponse
    recommended_alternatives: list[AlternativeMedicineResponse]
    llm_reasoning: str
    safety_validation: SafetyValidationResponse
    openfda_requests: list[str] = Field(default_factory=list)


class MedicineEnrichRequest(BaseModel):
    medicine_name: str = Field(min_length=1, max_length=255)


class MedicineEnrichResponse(BaseModel):
    medicine: MedicineResponse
    openfda_data_found: bool
    enriched_fields: list[str]
    openfda_requests: list[str] = Field(default_factory=list)

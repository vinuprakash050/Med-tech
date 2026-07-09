from __future__ import annotations

from pydantic import BaseModel, Field

from app.dto.medicine import RecommendationResponse


# ── Request ──────────────────────────────────────────────────────────────────
# (No Pydantic model needed for the multipart upload request;
#  FastAPI handles it with UploadFile directly in the route.)


# ── OCR / Parser intermediate types ──────────────────────────────────────────

class ParsedMedicine(BaseModel):
    """One medicine entry extracted by the LLM parser from raw OCR text."""

    medicine_name: str
    dosage: str | None = None
    dosage_form: str | None = None
    frequency: str | None = None
    duration: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class OCRResult(BaseModel):
    """Raw output from the OCR pipeline before LLM parsing."""

    raw_text: str
    word_count: int = 0
    preprocessing_applied: list[str] = Field(default_factory=list)


# ── Per-medicine result ───────────────────────────────────────────────────────

class PrescriptionMedicineResult(BaseModel):
    """
    Full result for one medicine extracted from the prescription.

    original_name   – exactly as OCR+LLM extracted it
    matched_name    – normalised name after HybridMedicineSearchService
    confidence      – LLM parser confidence (0–1)
    matched         – True when HybridSearch resolved the medicine
    recommendation  – existing RecommendationResponse (None if match failed)
    error           – human-readable reason when recommendation failed
    """

    original_name: str
    matched_name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    dosage: str | None = None
    dosage_form: str | None = None
    frequency: str | None = None
    duration: str | None = None
    matched: bool = False
    recommendation: RecommendationResponse | None = None
    error: str | None = None


# ── Summary ───────────────────────────────────────────────────────────────────

class PrescriptionSummary(BaseModel):
    medicines_detected: int = 0
    successfully_matched: int = 0
    failed_matches: int = 0
    warnings: list[str] = Field(default_factory=list)
    processing_confidence: float = Field(default=0.0, ge=0.0, le=100.0)


# ── Top-level response ────────────────────────────────────────────────────────

class PrescriptionAnalysisResponse(BaseModel):
    """
    Full response returned by POST /api/v1/prescription/analyze.

    patient_name / doctor / date are best-effort fields – the LLM
    is instructed to extract them only when clearly present.
    """

    patient_name: str | None = None
    doctor: str | None = None
    date: str | None = None
    summary: PrescriptionSummary
    medicines: list[PrescriptionMedicineResult]
    ocr_raw_text: str | None = None

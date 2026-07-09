from __future__ import annotations

"""
PrescriptionAnalysisService
===========================
Orchestrates the full prescription-to-recommendations pipeline:

    Image bytes
        ↓
    PrescriptionOCRService      (preprocessing + EasyOCR / Tesseract)
        ↓
    PrescriptionParserAgent     (LLM or heuristic → structured medicines)
        ↓
    HybridMedicineSearchService (name normalisation / matching)
        ↓
    MedicineRecommendationService (existing recommendation pipeline)
        ↓
    PrescriptionAnalysisResponse

Key design decisions
--------------------
- All recommendation calls are issued concurrently via asyncio.gather().
- If a single recommendation fails the medicine is still included in the
  response with `matched=False` and an `error` message — the whole
  prescription is never aborted.
- The HybridMedicineSearchService is used for name matching so the same
  fuzzy-search + FDA-fallback logic that powers the text search is reused.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.medicine_recommendation import MedicineRecommendationService
from app.agents.prescription_parser import PrescriptionParserAgent, PrescriptionParseResult
from app.agents.vision_prescription_parser import VisionPrescriptionParser
from app.core.config import get_settings
from app.core.exceptions import MedicineNotFoundError
from app.dto.prescription import (
    OCRResult,
    ParsedMedicine,
    PrescriptionAnalysisResponse,
    PrescriptionMedicineResult,
    PrescriptionSummary,
)
from app.integrations.openfda.client import OpenFDAClient
from app.integrations.openfda.service import OpenFDAMedicineEnrichmentService
from app.agents.medicine_insights_agent import MedicineInsightsAgent
from app.providers.base import BaseLLMProvider
from app.providers.factory import get_llm_provider
from app.repositories.medicine import MedicineRepository
from app.services.hybrid_medicine_search import HybridMedicineSearchService
from app.services.medicine_suggestion import MedicineSuggestionService
from app.services.prescription_ocr import PrescriptionOCRService

logger = logging.getLogger(__name__)


class PrescriptionAnalysisService:
    """
    Orchestrates OCR → parsing → matching → recommendation.

    This service is instantiated per-request (stateless except for the
    injected dependencies).
    """

    def __init__(
        self,
        session: AsyncSession,
        llm_provider: BaseLLMProvider,
        openfda_client: OpenFDAClient | None = None,
    ) -> None:
        self.session = session
        self.llm_provider = llm_provider
        self.openfda_client = openfda_client

        # Build shared sub-services (same pattern as medicines.py route factory)
        self._repository = MedicineRepository(session)
        self._ocr_service = PrescriptionOCRService()
        self._parser_agent = PrescriptionParserAgent(llm_provider=llm_provider)
        self._vision_parser = VisionPrescriptionParser(llm_provider=llm_provider)

        suggestion_service = MedicineSuggestionService(
            repository=self._repository,
            llm_provider=llm_provider,
        )
        hybrid_search = HybridMedicineSearchService(
            session=session,
            repository=self._repository,
            llm_provider=llm_provider,
            openfda_client=openfda_client,
        )
        enrichment_service: OpenFDAMedicineEnrichmentService | None = None
        if openfda_client is not None:
            enrichment_service = OpenFDAMedicineEnrichmentService(
                repository=self._repository,
                client=openfda_client,
            )

        insights_agent = MedicineInsightsAgent(llm_provider=llm_provider)

        self._recommendation_service = MedicineRecommendationService(
            repository=self._repository,
            llm_provider=llm_provider,
            session=session,
            suggestion_service=suggestion_service,
            hybrid_search_service=hybrid_search,
            enrichment_service=enrichment_service,
            insights_agent=insights_agent,
        )
        self._hybrid_search = hybrid_search

    # ── Public API ────────────────────────────────────────────────────────────

    async def analyze(
        self,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
        generic_preference: bool = True,
    ) -> PrescriptionAnalysisResponse:
        """
        Full pipeline from raw image bytes to a PrescriptionAnalysisResponse.

        Parameters
        ----------
        image_bytes:
            Raw bytes of the uploaded prescription image.
        content_type:
            MIME type (validated inside PrescriptionOCRService).
        generic_preference:
            Passed through to MedicineRecommendationService.

        Returns
        -------
        PrescriptionAnalysisResponse
        """
        # ── Step 1 + 2: OCR and Vision parse ─────────────────────────────────
        # When vision is available, run OCR and vision LLM in parallel.
        # OCR is still needed for raw_text in the response but is no longer
        # on the critical path.
        logger.info("prescription_analysis_start size=%d", len(image_bytes))

        if self.llm_provider.supports_vision:
            logger.info("prescription_parse_mode=vision parallel_ocr=true")
            # Run both concurrently — vision parse is the critical path,
            # OCR result is only needed for raw_text display and fallback.
            ocr_task = asyncio.create_task(
                self._safe_ocr(image_bytes, content_type)
            )
            vision_task = asyncio.create_task(
                self._vision_parser.parse_image(
                    image_bytes=image_bytes,
                    content_type=content_type,
                    ocr_text_fallback=None,  # don't wait for OCR
                )
            )
            parse_result, ocr_result = await asyncio.gather(vision_task, ocr_task)
            # If vision returned no medicines, retry with OCR text
            if not parse_result.medicines and ocr_result and ocr_result.raw_text:
                logger.info("vision_empty_retrying_with_ocr_text")
                parse_result = await self._parser_agent.parse(ocr_result.raw_text)
        else:
            logger.info("prescription_parse_mode=text_llm")
            ocr_result = await self._safe_ocr(image_bytes, content_type)
            parse_result = await self._parser_agent.parse(
                ocr_result.raw_text if ocr_result else ""
            )

        ocr_text = ocr_result.raw_text if ocr_result else None
        logger.info(
            "prescription_parse_done medicines=%d used_fallback=%s",
            len(parse_result.medicines),
            parse_result.used_fallback,
        )

        if not parse_result.medicines:
            return PrescriptionAnalysisResponse(
                patient_name=parse_result.patient_name,
                doctor=parse_result.doctor,
                date=parse_result.date,
                summary=PrescriptionSummary(
                    medicines_detected=0,
                    successfully_matched=0,
                    failed_matches=0,
                    warnings=["No medicines could be identified in the prescription."],
                    processing_confidence=0.0,
                ),
                medicines=[],
                ocr_raw_text=ocr_text,
            )

        # ── Step 3: Name matching + recommendations (concurrent) ──────────────
        medicine_results = await self._process_medicines_concurrently(
            parsed_medicines=parse_result.medicines,
            generic_preference=generic_preference,
        )

        # ── Step 4: Build summary ─────────────────────────────────────────────
        summary = self._build_summary(medicine_results, parse_result)

        logger.info(
            "prescription_analysis_done detected=%d matched=%d failed=%d",
            summary.medicines_detected,
            summary.successfully_matched,
            summary.failed_matches,
        )

        return PrescriptionAnalysisResponse(
            patient_name=parse_result.patient_name,
            doctor=parse_result.doctor,
            date=parse_result.date,
            summary=summary,
            medicines=medicine_results,
            ocr_raw_text=ocr_text,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _safe_ocr(
        self, image_bytes: bytes, content_type: str
    ) -> OCRResult | None:
        """Run OCR, returning None on failure so it never blocks the vision path."""
        try:
            result = await self._ocr_service.extract(image_bytes, content_type)
            logger.info("prescription_ocr_done words=%d", result.word_count)
            return result
        except Exception as exc:
            logger.warning("prescription_ocr_failed error=%s", exc)
            return None

    async def _process_medicines_concurrently(
        self,
        parsed_medicines: list[ParsedMedicine],
        generic_preference: bool,
    ) -> list[PrescriptionMedicineResult]:
        """
        Process medicines sequentially to avoid asyncpg session conflicts.

        asyncpg does not allow multiple queries on the same connection
        simultaneously. Running with asyncio.gather() over a shared session
        causes InterfaceError: cannot perform operation: another operation
        is in progress.

        Sequential processing is safe and the LLM calls (not DB queries)
        are the actual bottleneck anyway.
        """
        results: list[PrescriptionMedicineResult] = []
        for med in parsed_medicines:
            result = await self._process_single_medicine(med, generic_preference)
            results.append(result)
        return results

    async def _process_single_medicine(
        self,
        parsed: ParsedMedicine,
        generic_preference: bool,
    ) -> PrescriptionMedicineResult:
        """
        Attempt to match and recommend one medicine.
        Errors are caught so that a single failure never aborts the pipeline.
        """
        base = PrescriptionMedicineResult(
            original_name=parsed.medicine_name,
            confidence=parsed.confidence,
            dosage=parsed.dosage,
            dosage_form=parsed.dosage_form,
            frequency=parsed.frequency,
            duration=parsed.duration,
        )

        # ── Name matching via HybridSearch ────────────────────────────────────
        try:
            matched_medicine = await self._hybrid_search.resolve(parsed.medicine_name)
        except Exception as exc:
            logger.warning(
                "prescription_match_failed name=%s error=%s",
                parsed.medicine_name,
                exc,
            )
            matched_medicine = None

        if matched_medicine is None:
            logger.info("prescription_match_not_found name=%s", parsed.medicine_name)
            return base.model_copy(
                update={
                    "matched": False,
                    "error": "Medicine could not be identified in the database.",
                }
            )

        matched_name = matched_medicine.name

        # ── Recommendation ────────────────────────────────────────────────────
        try:
            recommendation = await self._recommendation_service.recommend(
                medicine_name=matched_name,
                generic_preference=generic_preference,
            )
            return base.model_copy(
                update={
                    "matched_name": matched_name,
                    "matched": True,
                    "recommendation": recommendation,
                }
            )
        except MedicineNotFoundError:
            logger.info("prescription_recommendation_not_found name=%s", matched_name)
            return base.model_copy(
                update={
                    "matched_name": matched_name,
                    "matched": False,
                    "error": "Medicine found but recommendation pipeline returned no results.",
                }
            )
        except Exception as exc:
            logger.warning(
                "prescription_recommendation_failed name=%s error=%s",
                matched_name,
                exc,
            )
            return base.model_copy(
                update={
                    "matched_name": matched_name,
                    "matched": False,
                    "error": f"Recommendation failed: {exc!s}",
                }
            )

    @staticmethod
    def _build_summary(
        results: list[PrescriptionMedicineResult],
        parse_result: PrescriptionParseResult,
    ) -> PrescriptionSummary:
        detected = len(results)
        matched = sum(1 for r in results if r.matched)
        failed = detected - matched

        warnings: list[str] = []
        if parse_result.used_fallback:
            warnings.append(
                "AI parsing was not available; medicines were extracted using basic pattern matching. "
                "Please verify the list."
            )
        for r in results:
            if not r.matched:
                warnings.append(f"Could not identify: {r.original_name}")

        # Average confidence across all extracted medicines
        if results:
            avg_confidence = sum(r.confidence for r in results) / len(results)
            # Penalise for failed matches
            match_rate = matched / detected if detected else 0.0
            processing_confidence = round(avg_confidence * match_rate * 100, 1)
        else:
            processing_confidence = 0.0

        return PrescriptionSummary(
            medicines_detected=detected,
            successfully_matched=matched,
            failed_matches=failed,
            warnings=warnings,
            processing_confidence=processing_confidence,
        )


# ── Factory helper (mirrors pattern in medicines.py) ─────────────────────────

def get_prescription_analysis_service(
    session: AsyncSession,
    openfda_client: OpenFDAClient | None = None,
) -> PrescriptionAnalysisService:
    settings = get_settings()
    provider = get_llm_provider(settings)
    return PrescriptionAnalysisService(
        session=session,
        llm_provider=provider,
        openfda_client=openfda_client,
    )

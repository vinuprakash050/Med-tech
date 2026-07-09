import re
from decimal import Decimal
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LLMProviderError, MedicineNotFoundError
from app.dto.medicine import (
    AlternativeMedicineResponse,
    MedicineResponse,
    RecommendationResponse,
    SafetyValidationResponse,
)
from app.integrations.openfda.service import OpenFDAMedicineEnrichmentService
from app.models.medicine import Medicine
from app.agents.medicine_insights_agent import MedicineInsightsAgent
from app.prompts.recommendation import build_recommendation_prompt
from app.providers.base import BaseLLMProvider
from app.repositories.medicine import MedicineRepository
from app.services.hybrid_medicine_search import HybridMedicineSearchService
from app.services.medicine_suggestion import MedicineSuggestionService


def _strip_markdown(text: str) -> str:
    """Remove common markdown formatting so the frontend receives plain prose."""
    # Remove fenced code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers (**text**, *text*, __text__, _text_)
    text = re.sub(r"\*{1,2}|_{1,2}", "", text)
    # Replace markdown bullet lines (*, -, •) with a plain dash so prose flows
    text = re.sub(r"^\s*[\*\-•]\s+", "- ", text, flags=re.MULTILINE)
    # Remove numbered list markers (1. 2. etc.)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Collapse excess blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fallback_reasoning(requested: Medicine, alternatives: list[Medicine]) -> str:
    if not alternatives:
        return (
            "No lower-priced alternative with the same salt composition and dosage "
            "was found in the database."
        )

    return (
        "These alternatives were selected from approved database records with the same "
        f"salt composition and dosage as {requested.name}. They are lower-priced options, "
        "with generic medicines preferred when requested."
    )


class MedicineRecommendationService:
    def __init__(
        self,
        repository: MedicineRepository,
        llm_provider: BaseLLMProvider,
        session: AsyncSession | None = None,
        suggestion_service: MedicineSuggestionService | None = None,
        hybrid_search_service: HybridMedicineSearchService | None = None,
        enrichment_service: OpenFDAMedicineEnrichmentService | None = None,
        insights_agent: MedicineInsightsAgent | None = None,
    ) -> None:
        self.repository = repository
        self.llm_provider = llm_provider
        self.session = session
        self.suggestion_service = suggestion_service
        self.hybrid_search_service = hybrid_search_service
        self.enrichment_service = enrichment_service
        self.insights_agent = insights_agent or MedicineInsightsAgent(llm_provider=llm_provider)

    async def recommend(
        self,
        medicine_name: str,
        generic_preference: bool = True,
    ) -> RecommendationResponse:
        requested_medicine = await self.repository.get_by_name(medicine_name)
        if not requested_medicine and self.hybrid_search_service is not None:
            requested_medicine = await self.hybrid_search_service.resolve(medicine_name)
        elif not requested_medicine and self.suggestion_service is not None:
            requested_medicine = await self.suggestion_service.resolve(medicine_name)
        if not requested_medicine:
            raise MedicineNotFoundError(f"Medicine '{medicine_name}' not found")

        alternatives = await self.repository.find_alternatives(
            source_medicine=requested_medicine,
            generic_preference=generic_preference,
        )

        requested_openfda_requests: list[str] = []
        alternative_enrichments: list[tuple[Medicine, list[str]]] = []
        if self.enrichment_service is not None:
            requested_enrichment = await self.enrichment_service.enrich(requested_medicine)
            requested_openfda_requests = requested_enrichment.api_calls
            for alternative in alternatives:
                alternative_enrichment = await self.enrichment_service.enrich(alternative)
                alternative_enrichments.append((alternative, alternative_enrichment.api_calls))
        else:
            alternative_enrichments = [(alternative, []) for alternative in alternatives]

        # AI-powered insights for the requested medicine — built from DB fields
        # directly (no LLM call). The fallback is thorough and instant.
        from app.agents.medicine_insights_agent import _build_fallback_insights
        requested_insights = _build_fallback_insights(requested_medicine)

        requested_response = MedicineResponse.model_validate(requested_medicine).model_copy(
            update={
                "openfda_requests": requested_openfda_requests,
                "medicine_insights": requested_insights,
            }
        )
        safety_validation = self._build_safety_validation(
            requested=requested_medicine,
            alternatives=alternatives,
        )
        prompt = build_recommendation_prompt(requested_medicine, alternatives)

        try:
            logger = logging.getLogger("app.llm")
            logger.info(
                "MedicineRecommendationService LLM call start provider=%s model=%s",
                type(self.llm_provider).__name__,
                getattr(self.llm_provider, "model", "unknown"),
            )
            logger.info("MedicineRecommendationService LLM call waiting provider=%s", type(self.llm_provider).__name__)

            llm_reasoning = await self.llm_provider.generate_response(prompt)
            logger.info("MedicineRecommendationService LLM call completed provider=%s", type(self.llm_provider).__name__)
            llm_reasoning = _strip_markdown(llm_reasoning)
        except LLMProviderError as exc:
            logging.getLogger("app.llm").warning(
                "MedicineRecommendationService LLM call failed provider=%s: %s",
                type(self.llm_provider).__name__,
                exc,
            )
            llm_reasoning = _fallback_reasoning(requested_medicine, alternatives)
        except Exception as exc:  # pragma: no cover
            logging.getLogger("app.llm").warning(
                "MedicineRecommendationService unexpected LLM failure provider=%s: %s",
                type(self.llm_provider).__name__,
                exc,
            )
            llm_reasoning = _fallback_reasoning(requested_medicine, alternatives)

        alternative_responses = []
        for alternative, openfda_requests in alternative_enrichments:
            alt_response = await self._to_alternative_response(
                requested_medicine, alternative, openfda_requests
            )
            alternative_responses.append(alt_response)

        openfda_requests = []
        for api_call in requested_openfda_requests:
            if api_call not in openfda_requests:
                openfda_requests.append(api_call)
        for _, enrichment_requests in alternative_enrichments:
            for api_call in enrichment_requests:
                if api_call not in openfda_requests:
                    openfda_requests.append(api_call)

        return RecommendationResponse(
            requested_medicine=requested_response,
            recommended_alternatives=alternative_responses,
            llm_reasoning=llm_reasoning,
            safety_validation=safety_validation,
            openfda_requests=openfda_requests,
        )

    def _build_safety_validation(
        self,
        requested: Medicine,
        alternatives: list[Medicine],
    ) -> SafetyValidationResponse:
        same_salt = all(
            medicine.salt_composition == requested.salt_composition
            for medicine in alternatives
        )
        same_dosage = all(medicine.dosage == requested.dosage for medicine in alternatives)
        return SafetyValidationResponse(same_salt=same_salt, same_dosage=same_dosage)

    async def _to_alternative_response(
        self,
        requested: Medicine,
        alternative: Medicine,
        openfda_requests: list[str] | None = None,
    ) -> AlternativeMedicineResponse:
        from app.agents.medicine_insights_agent import _build_fallback_insights
        alternative_payload = MedicineResponse.model_validate(alternative).model_dump(
            exclude={"openfda_requests", "medicine_insights"}
        )
        # Build insights from DB fields — no LLM call, instant
        alt_insights = _build_fallback_insights(alternative, reference_medicine=requested)
        return AlternativeMedicineResponse(
            **alternative_payload,
            price_difference=Decimal(requested.price) - Decimal(alternative.price),
            same_salt=alternative.salt_composition == requested.salt_composition,
            same_dosage=alternative.dosage == requested.dosage,
            openfda_requests=openfda_requests or [],
            medicine_insights=alt_insights,
        )

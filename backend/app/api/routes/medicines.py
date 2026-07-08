from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_session
from app.dto.medicine import (
    MedicineEnrichRequest,
    MedicineEnrichResponse,
    MedicineResponse,
    MedicineSearchRequest,
    MedicineSuggestionRequest,
    MedicineSuggestionResponse,
    RecommendationResponse,
)
from app.integrations.openfda.service import OpenFDAMedicineEnrichmentService
from app.providers.factory import get_llm_provider
from app.repositories.medicine import MedicineRepository
from app.services.hybrid_medicine_search import HybridMedicineSearchService
from app.agents.medicine_insights_agent import MedicineInsightsAgent
from app.agents.medicine_recommendation import MedicineRecommendationService
from app.services.medicine_suggestion import MedicineSuggestionService

router = APIRouter(prefix="/medicine", tags=["medicine"])
list_router = APIRouter(prefix="/medicines", tags=["medicines"])


def get_recommendation_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> MedicineRecommendationService:
    settings = get_settings()
    repository = MedicineRepository(session)
    provider = get_llm_provider(settings)
    suggestion_service = MedicineSuggestionService(repository=repository, llm_provider=provider)
    hybrid_search_service = get_hybrid_search_service(request=request, session=session)
    enrichment_service = get_openfda_enrichment_service(request=request, session=session)
    insights_agent = MedicineInsightsAgent(llm_provider=provider)
    return MedicineRecommendationService(
        repository=repository,
        llm_provider=provider,
        suggestion_service=suggestion_service,
        hybrid_search_service=hybrid_search_service,
        enrichment_service=enrichment_service,
        insights_agent=insights_agent,
    )


def get_openfda_enrichment_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> OpenFDAMedicineEnrichmentService:
    repository = MedicineRepository(session)
    client = request.app.state.openfda_client
    return OpenFDAMedicineEnrichmentService(repository=repository, client=client)


def get_hybrid_search_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> HybridMedicineSearchService:
    settings = get_settings()
    repository = MedicineRepository(session)
    provider = get_llm_provider(settings)
    openfda_client = request.app.state.openfda_client
    return HybridMedicineSearchService(
        session=session,
        repository=repository,
        llm_provider=provider,
        openfda_client=openfda_client,
    )


def get_medicine_suggestion_service(
    session: AsyncSession = Depends(get_db_session),
) -> MedicineSuggestionService:
    settings = get_settings()
    repository = MedicineRepository(session)
    provider = get_llm_provider(settings)
    return MedicineSuggestionService(repository=repository, llm_provider=provider)


@router.post("/recommend", response_model=RecommendationResponse, response_model_exclude_none=True)
async def recommend_medicine(
    payload: MedicineSearchRequest,
    service: MedicineRecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    return await service.recommend(
        medicine_name=payload.medicine_name,
        generic_preference=payload.generic_preference,
    )


@router.post("/suggest", response_model=MedicineSuggestionResponse, response_model_exclude_none=True)
async def suggest_medicine(
    payload: MedicineSuggestionRequest,
    service: HybridMedicineSearchService = Depends(get_hybrid_search_service),
) -> MedicineSuggestionResponse:
    hybrid_result = await service.suggest(payload.query)
    return MedicineSuggestionResponse(
        original_query=payload.query,
        suggestions=hybrid_result.suggestions,
        fda_fallback_used=hybrid_result.fda_fallback_used,
        fda_search_term=hybrid_result.fda_search_term,
    )


@router.post("/enrich", response_model=MedicineEnrichResponse, response_model_exclude_none=True)
async def enrich_medicine(
    payload: MedicineEnrichRequest,
    request: Request,
    service: OpenFDAMedicineEnrichmentService = Depends(get_openfda_enrichment_service),
) -> MedicineEnrichResponse:
    settings = get_settings()
    provider = get_llm_provider(settings)
    insights_agent = MedicineInsightsAgent(llm_provider=provider)

    result = await service.enrich_by_name(payload.medicine_name)
    insights = await insights_agent.build(result.medicine)

    return MedicineEnrichResponse(
        medicine=MedicineResponse.model_validate(result.medicine).model_copy(
            update={
                "openfda_requests": result.api_calls,
                "medicine_insights": insights,
            }
        ),
        openfda_data_found=result.openfda_data_found,
        enriched_fields=result.enriched_fields,
        openfda_requests=result.api_calls,
    )


@list_router.get("", response_model=list[MedicineResponse], response_model_exclude_none=True)
async def get_medicines(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> list[MedicineResponse]:
    repository = MedicineRepository(session)
    medicines = await repository.list_medicines(skip=skip, limit=limit)
    return [MedicineResponse.model_validate(medicine) for medicine in medicines]

from __future__ import annotations

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher, get_close_matches

from app.core.exceptions import LLMProviderError
from app.dto.medicine import MedicineSuggestionItem, MedicineSuggestionResponse
from app.models.medicine import Medicine
from app.prompts.search_suggestion import build_search_suggestion_prompt
from app.providers.base import BaseLLMProvider
from app.repositories.medicine import MedicineRepository
from app.utils.medicine_search import normalize_medicine_text

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _RankedCandidate:
    medicine: Medicine
    score: float
    reason: str


class MedicineSuggestionService:
    def __init__(
        self,
        repository: MedicineRepository,
        llm_provider: BaseLLMProvider,
        search_pool_limit: int = 500,
    ) -> None:
        self.repository = repository
        self.llm_provider = llm_provider
        self.search_pool_limit = search_pool_limit

    async def suggest(self, query: str, limit: int = 5) -> MedicineSuggestionResponse:
        normalized_query = normalize_medicine_text(query)
        if not normalized_query:
            return MedicineSuggestionResponse(original_query=query, suggestions=[])

        ranked_candidates = await self._rank_candidates(normalized_query, limit=max(limit, 10))
        suggestions = [
            MedicineSuggestionItem(
                medicine_name=candidate.medicine.name,
                confidence=self._to_confidence(candidate.score),
                reason=candidate.reason,
            )
            for candidate in ranked_candidates[:limit]
        ]
        return MedicineSuggestionResponse(original_query=query, suggestions=suggestions)

    async def resolve(self, query: str) -> Medicine | None:
        normalized_query = normalize_medicine_text(query)
        if not normalized_query:
            return None

        exact_match = await self.repository.get_by_name(query)
        if exact_match is not None:
            return exact_match

        ranked_candidates = await self._rank_candidates(normalized_query, limit=5)
        if not ranked_candidates:
            return None

        candidate_names = [candidate.medicine.name for candidate in ranked_candidates[:5]]
        best_guess_name = await self._ask_llm_for_best_candidate(query, candidate_names)
        if best_guess_name is None:
            best_guess_name = ranked_candidates[0].medicine.name

        for candidate in ranked_candidates:
            if candidate.medicine.name == best_guess_name:
                return candidate.medicine

        return ranked_candidates[0].medicine

    async def _rank_candidates(self, normalized_query: str, limit: int) -> list[_RankedCandidate]:
        partial_matches = await self.repository.search_medicine_candidates(normalized_query, limit=50)
        search_pool = await self.repository.list_medicine_search_pool(limit=self.search_pool_limit)

        candidates_by_id: dict[int, Medicine] = {}
        for medicine in partial_matches + search_pool:
            candidates_by_id[medicine.id] = medicine

        if not candidates_by_id:
            return []

        search_names = [normalize_medicine_text(medicine.name) for medicine in candidates_by_id.values()]
        close_matches = set(get_close_matches(normalized_query, search_names, n=min(limit, len(search_names)), cutoff=0.2))
        partial_match_ids = {medicine.id for medicine in partial_matches}

        ranked_candidates: list[_RankedCandidate] = []
        for medicine in candidates_by_id.values():
            name_score = self._similarity(normalized_query, medicine.name)
            generic_score = self._similarity(normalized_query, medicine.generic_name)
            salt_score = self._similarity(normalized_query, medicine.salt_composition)

            score = max(name_score, generic_score * 0.92, salt_score * 0.75)
            reason_parts: list[str] = []

            if normalize_medicine_text(medicine.name) == normalized_query:
                score = 1.0
                reason_parts.append("Exact database match")
            elif medicine.id in partial_match_ids:
                score += 0.12
                reason_parts.append("Partial database match")

            normalized_name = normalize_medicine_text(medicine.name)
            if normalized_name in close_matches:
                score += 0.08
                reason_parts.append("Close spelling match")

            if not reason_parts:
                reason_parts.append("Closest semantic and spelling match")

            score = min(score, 1.0)
            ranked_candidates.append(
                _RankedCandidate(
                    medicine=medicine,
                    score=score,
                    reason=", ".join(dict.fromkeys(reason_parts)),
                )
            )

        ranked_candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.medicine.is_generic is False,
                candidate.medicine.price,
                candidate.medicine.name,
            )
        )

        ai_choice = await self._ask_llm_for_best_candidate(
            normalized_query,
            [candidate.medicine.name for candidate in ranked_candidates[:5]],
        )
        if ai_choice:
            for index, candidate in enumerate(ranked_candidates):
                if candidate.medicine.name == ai_choice:
                    boosted_score = min(candidate.score + 0.1, 1.0)
                    ranked_candidates[index] = _RankedCandidate(
                        medicine=candidate.medicine,
                        score=boosted_score,
                        reason=f"{candidate.reason}, AI confirmed",
                    )
                    break

            ranked_candidates.sort(
                key=lambda candidate: (
                    -candidate.score,
                    candidate.medicine.is_generic is False,
                    candidate.medicine.price,
                    candidate.medicine.name,
                )
            )

        return ranked_candidates[:limit]

    async def _ask_llm_for_best_candidate(
        self,
        query: str,
        candidate_names: list[str],
    ) -> str | None:
        if not candidate_names:
            return None

        prompt = build_search_suggestion_prompt(query=query, candidate_names=candidate_names)
        try:
            raw_response = await self.llm_provider.generate_response(prompt)
        except LLMProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            raise LLMProviderError(f"Unexpected LLM provider failure: {exc}") from exc

        normalized_response = raw_response.strip().strip('"').strip("'")
        for candidate_name in candidate_names:
            if candidate_name.lower() == normalized_response.lower():
                return candidate_name

        for candidate_name in candidate_names:
            if candidate_name.lower() in normalized_response.lower():
                return candidate_name

        logger.info(
            "medicine_suggestion_llm_unresolved query=%s response=%s",
            query,
            normalized_response,
        )
        return None

    def _similarity(self, query: str, value: str | None) -> float:
        if not value:
            return 0.0
        return SequenceMatcher(None, query, normalize_medicine_text(value)).ratio()

    def _to_confidence(self, score: float) -> int:
        return max(1, min(100, round(score * 100)))


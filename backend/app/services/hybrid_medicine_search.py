from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher, get_close_matches

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import LLMProviderError, OpenFDAIntegrationError
from app.dto.medicine import MedicineSuggestionItem, MedicineSuggestionResponse
from app.integrations.openfda.client import OpenFDAClient
from app.integrations.openfda.mapper import map_openfda_record
from app.models.medicine import Medicine
from app.prompts.search_suggestion import build_search_suggestion_prompt
from app.repositories.medicine import MedicineRepository
from app.utils.fda_search_utils import extract_generic_term, normalize_fda_search_term, truncate_field
from app.utils.medicine_search import normalize_medicine_text

logger = logging.getLogger(__name__)

CONFIDENCE_EXACT_MATCH = 100
CONFIDENCE_HIGH = 85
CONFIDENCE_MEDIUM = 60
CONFIDENCE_LOW = 40

# Minimum confidence to consider DB results sufficient (skip FDA)
DB_CONFIDENCE_THRESHOLD = 75


@dataclass(slots=True)
class _RankedCandidate:
    medicine: Medicine
    score: float
    reason: str
    source_tag: str = "DB"


@dataclass(slots=True)
class HybridSearchResult:
    suggestions: list[MedicineSuggestionItem]
    fda_fallback_used: bool = False
    db_results_count: int = 0
    fda_results_count: int = 0
    fda_search_term: str | None = None


class HybridMedicineSearchService:
    """Hybrid medicine search service combining local DB + FDA fallback.

    Architecture:
        User Input
            ↓
        Local DB fuzzy search
            ↓
        Confidence evaluation
            ↓
        If low confidence or no results:
            ↓
        FDA generic search fallback
            ↓
        Normalize FDA response
            ↓
        Store/cache medicine locally
            ↓
        Combine DB + FDA candidates
            ↓
        AI semantic reasoning
            ↓
        Frontend suggestions
    """

    def __init__(
        self,
        session: AsyncSession,
        repository: MedicineRepository,
        llm_provider,
        openfda_client: OpenFDAClient | None = None,
        search_pool_limit: int = 500,
    ) -> None:
        self.session = session
        self.repository = repository
        self.llm_provider = llm_provider
        self.openfda_client = openfda_client
        self.search_pool_limit = search_pool_limit

    async def suggest(self, query: str, limit: int = 5) -> HybridSearchResult:
        """Main entry point for hybrid suggest flow."""
        normalized_query = normalize_medicine_text(query)
        if not normalized_query:
            return HybridSearchResult(
                suggestions=[],
                fda_fallback_used=False,
            )

        # Step 1: Local DB fuzzy search + confidence evaluation
        db_candidates = await self._search_db(normalized_query, limit=10)
        best_confidence = db_candidates[0].score if db_candidates else 0.0

        result = HybridSearchResult(
            suggestions=[],
            db_results_count=len(db_candidates),
            fda_fallback_used=False,
        )

        # Step 2: If high confidence from DB, skip FDA
        if best_confidence >= (DB_CONFIDENCE_THRESHOLD / 100.0):
            logger.info(
                "hybrid_search_db_sufficient query=%s confidence=%s candidates=%s",
                normalized_query,
                round(best_confidence, 2),
                len(db_candidates),
            )
            ranked = await self._rank_and_ai_sort(normalized_query, db_candidates, limit=max(limit, 10))
            result.suggestions = self._to_suggestions(ranked, limit)
            return result

        # Step 3: Low confidence — trigger FDA fallback
        if self.openfda_client is None:
            ranked = await self._rank_and_ai_sort(normalized_query, db_candidates, limit=max(limit, 10))
            result.suggestions = self._to_suggestions(ranked, limit)
            return result

        fda_term = extract_generic_term(query)
        result.fda_fallback_used = True
        result.fda_search_term = fda_term

        logger.info(
            "hybrid_search_fda_fallback query=%s normalized=%s fda_term=%s db_candidates=%s",
            query,
            normalized_query,
            fda_term,
            len(db_candidates),
        )

        # Step 4: Search FDA
        fda_candidates = await self._search_fda_and_cache(fda_term)
        result.fda_results_count = len(fda_candidates)

        # Step 5: Combine DB + FDA candidates
        combined = self._merge_candidates(db_candidates, fda_candidates)

        # Step 6: AI semantic ranking
        ranked = await self._rank_and_ai_sort(normalized_query, combined, limit=max(limit, 10))
        result.suggestions = self._to_suggestions(ranked, limit)
        return result

    async def resolve(self, query: str) -> Medicine | None:
        """Resolve a user query to the best matching Medicine record.

        Tries exact match first, then hybrid search with AI disambiguation.
        """
        normalized_query = normalize_medicine_text(query)
        if not normalized_query:
            return None

        # Try exact match first
        exact_match = await self.repository.get_by_name(query)
        if exact_match is not None:
            return exact_match

        # Try exact match via normalized name
        stmt = select(Medicine).where(func.lower(Medicine.normalized_name) == normalized_query)
        result = await self.session.execute(stmt)
        exact_normalized = result.scalar_one_or_none()
        if exact_normalized is not None:
            return exact_normalized

        # Hybrid search for best candidate — take top DB result directly.
        # The fuzzy scorer already ranks by string similarity + partial match,
        # so candidate_names[0] is the best match without needing an LLM call.
        hybrid_result = await self.suggest(query, limit=5)
        if not hybrid_result.suggestions:
            return None

        candidate_names = [s.medicine_name for s in hybrid_result.suggestions[:5]]
        if not candidate_names:
            return None

        best_name = candidate_names[0]
        return await self.repository.get_by_name(best_name)

    async def _search_db(self, normalized_query: str, limit: int) -> list[_RankedCandidate]:
        """Search local DB for medicine candidates."""
        partial_matches = await self.repository.search_medicine_candidates(normalized_query, limit=50)
        search_pool = await self.repository.list_medicine_search_pool(limit=self.search_pool_limit)

        candidates_by_id: dict[int, Medicine] = {}
        for medicine in partial_matches + search_pool:
            candidates_by_id[medicine.id] = medicine

        if not candidates_by_id:
            return []

        search_names = [normalize_medicine_text(m.name) for m in candidates_by_id.values()]
        close_matches = set(
            get_close_matches(normalized_query, search_names, n=min(limit, len(search_names)), cutoff=0.2)
        )
        partial_match_ids = {m.id for m in partial_matches}

        ranked: list[_RankedCandidate] = []
        for medicine in candidates_by_id.values():
            score, reason_parts = self._compute_db_score(normalized_query, medicine, partial_match_ids, close_matches)
            ranked.append(
                _RankedCandidate(
                    medicine=medicine,
                    score=score,
                    reason=", ".join(dict.fromkeys(reason_parts)),
                )
            )

        ranked.sort(key=lambda c: (-c.score, c.medicine.is_generic is False, c.medicine.price, c.medicine.name))
        return ranked[:limit]

    def _compute_db_score(
        self,
        normalized_query: str,
        medicine: Medicine,
        partial_match_ids: set[int],
        close_matches: set[str],
    ) -> tuple[float, list[str]]:
        """Compute a confidence score for a DB medicine match."""
        reason_parts: list[str] = []
        score = 0.0

        name_score = SequenceMatcher(None, normalized_query, normalize_medicine_text(medicine.name)).ratio()
        generic_score = SequenceMatcher(None, normalized_query, normalize_medicine_text(medicine.generic_name or "")).ratio()
        salt_score = SequenceMatcher(None, normalized_query, normalize_medicine_text(medicine.salt_composition)).ratio()
        normalized_name_score = SequenceMatcher(None, normalized_query, normalize_medicine_text(medicine.normalized_name or "")).ratio()

        score = max(name_score, generic_score * 0.92, salt_score * 0.75, normalized_name_score * 0.95)

        # Exact match
        if normalize_medicine_text(medicine.name) == normalized_query:
            score = 1.0
            reason_parts.append("Exact match")
        elif normalize_medicine_text(medicine.normalized_name or "") == normalized_query:
            score = max(score, 0.95)
            reason_parts.append("Exact normalized match")
        elif medicine.id in partial_match_ids:
            score += 0.12
            source_tag = "FDA" if medicine.fda_cached else "DB"
            reason_parts.append(f"{source_tag} partial match")

        # Close spelling match
        normalized_name = normalize_medicine_text(medicine.name)
        if normalized_name in close_matches:
            score += 0.08
            reason_parts.append("Close spelling match")

        if not reason_parts:
            if medicine.fda_cached:
                reason_parts.append("FDA cached match")
            else:
                reason_parts.append("Similar match")

        score = min(score, 1.0)
        return score, reason_parts

    async def _search_fda_and_cache(self, generic_term: str) -> list[Medicine]:
        """Search FDA using generic_name and cache results locally."""
        if self.openfda_client is None:
            return []

        search_query = f'openfda.generic_name:"{generic_term.upper()}"'

        try:
            response = await self.openfda_client.search_labels(search_query=search_query, limit=3)
        except OpenFDAIntegrationError as exc:
            logger.warning(
                "hybrid_search_fda_failure term=%s error=%s",
                generic_term,
                exc.__class__.__name__,
            )
            return []

        if not response.results:
            logger.info("hybrid_search_fda_no_results term=%s", generic_term)
            return []

        cached_medicines: list[Medicine] = []
        for record in response.results:
            update = map_openfda_record(record)
            if not update.generic_name:
                continue

            fda_generic_name = update.generic_name.strip()
            medicine = await self._cache_fda_result(fda_generic_name, update)
            if medicine is not None:
                cached_medicines.append(medicine)

        return cached_medicines

    async def _cache_fda_result(
        self,
        medicine_name: str,
        update,
    ) -> Medicine | None:
        """Insert or update a medicine record from FDA data into the local DB."""
        normalized = normalize_medicine_text(medicine_name)
        if not normalized:
            return None

        # Check if already exists by name
        existing = await self.repository.get_by_name(medicine_name)
        if existing is not None:
            # Update FDA fields if newer data
            await self._apply_fda_update(existing, update)
            return existing

        # Check if exists by normalized_name
        stmt = select(Medicine).where(func.lower(Medicine.normalized_name) == normalized)
        result = await self.session.execute(stmt)
        existing_normalized = result.scalar_one_or_none()
        if existing_normalized is not None:
            await self._apply_fda_update(existing_normalized, update)
            return existing_normalized

        # Create new medicine record from FDA data
        now = datetime.now(timezone.utc)
        db_updates = update.as_db_updates()

        medicine = Medicine(
            name=medicine_name,
            salt_composition=update.active_ingredients or medicine_name,
            dosage="N/A",
            manufacturer=update.manufacturer_name or "FDA Unknown",
            medicine_type="Unknown",
            price=0.0,
            is_generic=True,
            approval_status="approved",
            generic_name=update.generic_name,
            active_ingredients=truncate_field(update.active_ingredients),
            dosage_form=truncate_field(update.dosage_form),
            warnings=truncate_field(update.warnings),
            adverse_reactions=truncate_field(update.adverse_reactions),
            indications=truncate_field(update.indications),
            purpose=truncate_field(update.purpose),
            common_side_effects=truncate_field(update.adverse_reactions),
            source="FDA",
            fda_cached=True,
            normalized_name=normalized,
            last_fda_sync_at=now,
            openfda_synced_at=now,
        )
        self.session.add(medicine)
        await self.session.commit()
        await self.session.refresh(medicine)

        logger.info(
            "hybrid_search_fda_cached_new name=%s generic=%s",
            medicine_name,
            update.generic_name,
        )
        return medicine

    async def _apply_fda_update(self, medicine: Medicine, update) -> None:
        """Update existing medicine with FDA data if fields are missing."""
        now = datetime.now(timezone.utc)
        updated = False

        db_updates = update.as_db_updates()
        for field_name, value in db_updates.items():
            if value and not getattr(medicine, field_name):
                setattr(medicine, field_name, truncate_field(value))
                updated = True

        if update.manufacturer_name and medicine.manufacturer in ("Unknown", "FDA Unknown", ""):
            medicine.manufacturer = update.manufacturer_name
            updated = True

        if updated:
            medicine.fda_cached = True
            medicine.last_fda_sync_at = now
            medicine.openfda_synced_at = now
            if not medicine.normalized_name:
                medicine.normalized_name = normalize_medicine_text(medicine.name)
            await self.session.commit()
            await self.session.refresh(medicine)

            logger.info(
                "hybrid_search_fda_updated_existing name=%s",
                medicine.name,
            )

    def _merge_candidates(
        self,
        db_candidates: list[_RankedCandidate],
        fda_candidates: list[Medicine],
    ) -> list[_RankedCandidate]:
        """Merge DB and FDA candidates, deduplicating by name."""
        seen_names: set[str] = set()
        merged: list[_RankedCandidate] = []

        # Add DB candidates first (higher priority)
        for candidate in db_candidates:
            key = normalize_medicine_text(candidate.medicine.name)
            if key not in seen_names:
                seen_names.add(key)
                merged.append(candidate)

        # Add FDA candidates with base score
        for medicine in fda_candidates:
            key = normalize_medicine_text(medicine.name)
            if key not in seen_names:
                seen_names.add(key)
                # FDA candidates get a moderate base score
                merged.append(
                    _RankedCandidate(
                        medicine=medicine,
                        score=0.65,
                        reason="FDA discovery match",
                        source_tag="FDA",
                    )
                )

        return merged

    async def _rank_and_ai_sort(
        self,
        normalized_query: str,
        candidates: list[_RankedCandidate],
        limit: int,
    ) -> list[_RankedCandidate]:
        """Rank candidates by fuzzy score — no LLM call needed here."""
        if not candidates:
            return []

        candidates.sort(key=lambda c: (-c.score, c.medicine.is_generic is False, c.medicine.price, c.medicine.name))
        return candidates[:limit]

    async def _ask_llm_for_best(
        self,
        query: str,
        candidate_names: list[str],
    ) -> str | None:
        """Ask LLM to pick the best candidate from a list."""
        if not candidate_names:
            return None

        prompt = build_search_suggestion_prompt(query=query, candidate_names=candidate_names)
        try:
            raw_response = await self.llm_provider.generate_response(prompt)
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"Unexpected LLM provider failure: {exc}") from exc

        normalized_response = raw_response.strip().strip('"').strip("'")
        for candidate_name in candidate_names:
            if candidate_name.lower() == normalized_response.lower():
                return candidate_name

        for candidate_name in candidate_names:
            if candidate_name.lower() in normalized_response.lower():
                return candidate_name

        logger.info(
            "hybrid_search_llm_unresolved query=%s response=%s candidates=%s",
            query,
            normalized_response,
            candidate_names,
        )
        return None

    def _to_suggestions(
        self,
        ranked: list[_RankedCandidate],
        limit: int,
    ) -> list[MedicineSuggestionItem]:
        """Convert ranked candidates to suggestion items."""
        items: list[MedicineSuggestionItem] = []
        for candidate in ranked[:limit]:
            confidence = max(1, min(100, round(candidate.score * 100)))
            reason = candidate.reason
            if candidate.medicine.fda_cached:
                reason = f"{reason} (FDA verified generic)"
            items.append(
                MedicineSuggestionItem(
                    medicine_name=candidate.medicine.name,
                    confidence=confidence,
                    reason=reason,
                )
            )
        return items
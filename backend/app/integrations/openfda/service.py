from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.core.exceptions import MedicineNotFoundError, OpenFDAIntegrationError
from app.integrations.openfda.client import OpenFDAClient
from app.integrations.openfda.mapper import OpenFDAMedicineUpdate, map_openfda_record
from app.models.medicine import Medicine
from app.repositories.medicine import MedicineRepository

logger = logging.getLogger(__name__)
OPENFDA_REFRESH_WINDOW = timedelta(days=7)


@dataclass(slots=True)
class OpenFDAMedicineEnrichmentResult:
    medicine: Medicine
    openfda_data_found: bool
    enriched_fields: list[str]
    api_calls: list[str] = field(default_factory=list)


class OpenFDAMedicineEnrichmentService:
    def __init__(
        self,
        repository: MedicineRepository,
        client: OpenFDAClient,
    ) -> None:
        self.repository = repository
        self.session = repository.session
        self.client = client

    async def enrich_by_name(
        self,
        medicine_name: str,
        force_refresh: bool = False,
    ) -> OpenFDAMedicineEnrichmentResult:
        medicine = await self.repository.get_by_name(medicine_name)
        if medicine is None:
            raise MedicineNotFoundError(f"Medicine '{medicine_name}' not found")
        return await self.enrich(medicine=medicine, force_refresh=force_refresh)

    async def enrich(
        self,
        medicine: Medicine,
        force_refresh: bool = False,
    ) -> OpenFDAMedicineEnrichmentResult:
        query_sources = self._build_query_sources(medicine)
        api_calls = self._build_api_calls(query_sources)

        if not force_refresh and self._is_fresh(medicine):
            logger.info(
                "openfda_enrichment_skipped medicine=%s reason=cached",
                medicine.name,
            )
            return OpenFDAMedicineEnrichmentResult(
                medicine=medicine,
                openfda_data_found=medicine.fda_data_available,
                enriched_fields=[],
                api_calls=api_calls,
            )

        for source_label, queries in query_sources:
            for search_query in queries:
                try:
                    response = await self.client.search_labels(search_query=search_query, limit=5)
                except OpenFDAIntegrationError as exc:
                    logger.warning(
                        "openfda_request_failure medicine=%s source=%s query=%s error=%s",
                        medicine.name,
                        source_label,
                        search_query,
                        exc.__class__.__name__,
                    )
                    continue

                if not response.results:
                    logger.info(
                        "openfda_no_records_found medicine=%s source=%s query=%s",
                        medicine.name,
                        source_label,
                        search_query,
                    )
                    continue

                openfda_record = response.results[0]
                update = map_openfda_record(openfda_record)
                enriched_fields = await self._apply_update(medicine, update)
                logger.info(
                    "openfda_enrichment_completed medicine=%s source=%s query=%s enriched_fields=%s",
                    medicine.name,
                    source_label,
                    search_query,
                    ",".join(enriched_fields) if enriched_fields else "none",
                )
                return OpenFDAMedicineEnrichmentResult(
                    medicine=medicine,
                    openfda_data_found=True,
                    enriched_fields=enriched_fields,
                    api_calls=api_calls,
                )

        medicine.openfda_synced_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(medicine)
        logger.info("openfda_enrichment_completed medicine=%s source=none enriched_fields=none", medicine.name)
        return OpenFDAMedicineEnrichmentResult(
            medicine=medicine,
            openfda_data_found=False,
            enriched_fields=[],
            api_calls=api_calls,
        )

    async def enrich_many(
        self,
        medicines: list[Medicine],
        force_refresh: bool = False,
    ) -> list[OpenFDAMedicineEnrichmentResult]:
        results: list[OpenFDAMedicineEnrichmentResult] = []
        for medicine in medicines:
            results.append(await self.enrich(medicine, force_refresh=force_refresh))
        return results

    async def _apply_update(
        self,
        medicine: Medicine,
        update: OpenFDAMedicineUpdate,
    ) -> list[str]:
        enriched_fields: list[str] = []
        db_updates = update.as_db_updates()

        for field_name, value in db_updates.items():
            if value and getattr(medicine, field_name) != value:
                setattr(medicine, field_name, value)
                enriched_fields.append(field_name)

        if update.manufacturer_name and not medicine.manufacturer:
            medicine.manufacturer = update.manufacturer_name
            enriched_fields.append("manufacturer")

        medicine.openfda_synced_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(medicine)
        return enriched_fields or update.enriched_fields

    def _build_query_sources(self, medicine: Medicine) -> list[tuple[str, list[str]]]:
        brand_candidates = self._build_brand_candidates(medicine.name)
        generic_candidates = self._build_generic_candidates(medicine)
        return [
            ("brand_name", [f'openfda.brand_name:"{candidate}"' for candidate in brand_candidates]),
            ("generic_name", [f'openfda.generic_name:"{candidate}"' for candidate in generic_candidates]),
        ]

    def _build_api_calls(self, query_sources: list[tuple[str, list[str]]]) -> list[str]:
        api_calls: list[str] = []
        for _, queries in query_sources:
            for search_query in queries:
                request_url = self.client.build_label_request_url(search_query=search_query, limit=5)
                if request_url not in api_calls:
                    api_calls.append(request_url)
        return api_calls

    def _build_brand_candidates(self, medicine_name: str) -> list[str]:
        normalized = self._normalize_search_term(medicine_name)
        candidates: list[str] = []
        if normalized:
            candidates.append(normalized)

        stripped = re.sub(r"\b\d+\s*MG\b", "", normalized).strip()
        stripped = re.sub(r"\b\d+\b", "", stripped).strip()
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if stripped and stripped not in candidates:
            candidates.append(stripped)

        if normalized:
            first_token = normalized.split()[0]
            if first_token not in candidates:
                candidates.append(first_token)

        return candidates

    def _build_generic_candidates(self, medicine: Medicine) -> list[str]:
        candidates = [self._normalize_search_term(medicine.salt_composition)]
        if medicine.generic_name:
            candidates.insert(0, self._normalize_search_term(medicine.generic_name))
        return [candidate for candidate in candidates if candidate]

    def _normalize_search_term(self, value: str) -> str:
        normalized = value.upper().strip()
        normalized = re.sub(r"[^A-Z0-9\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _is_fresh(self, medicine: Medicine) -> bool:
        if medicine.openfda_synced_at is None:
            return False
        return datetime.now(timezone.utc) - medicine.openfda_synced_at <= OPENFDA_REFRESH_WINDOW

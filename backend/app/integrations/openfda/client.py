from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlencode

import httpx

from app.core.exceptions import OpenFDAIntegrationError
from app.integrations.openfda.schemas import OpenFDALabelResponse

logger = logging.getLogger(__name__)


class OpenFDAClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max(1, max_retries)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    def build_label_request_url(self, search_query: str, limit: int = 1) -> str:
        params: dict[str, str] = {"search": search_query, "limit": str(limit)}
        if self.api_key:
            params["api_key"] = self.api_key
        return f"{self.base_url}/drug/label.json?{urlencode(params)}"

    async def search_labels(self, search_query: str, limit: int = 1) -> OpenFDALabelResponse:
        params: dict[str, str | int] = {"search": search_query, "limit": limit}
        if self.api_key:
            params["api_key"] = self.api_key

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._client.get("/drug/label.json", params=params)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
                last_error = exc
                logger.warning(
                    "openfda_request_failure query=%s attempt=%s error=%s",
                    search_query,
                    attempt,
                    exc.__class__.__name__,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise OpenFDAIntegrationError("openFDA request failed") from exc

            if response.status_code in {400, 404}:
                logger.info(
                    "openfda_request_no_records query=%s status=%s",
                    search_query,
                    response.status_code,
                )
                return OpenFDALabelResponse(results=[])

            if response.status_code in {429, 500, 502, 503, 504}:
                logger.warning(
                    "openfda_request_retryable_failure query=%s status=%s attempt=%s",
                    search_query,
                    response.status_code,
                    attempt,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise OpenFDAIntegrationError(
                    f"openFDA request failed with status {response.status_code}"
                )

            if response.status_code >= 400:
                logger.error(
                    "openfda_request_failure query=%s status=%s",
                    search_query,
                    response.status_code,
                )
                raise OpenFDAIntegrationError(
                    f"openFDA request failed with status {response.status_code}"
                )

            logger.info(
                "openfda_request_success query=%s status=%s",
                search_query,
                response.status_code,
            )
            try:
                return OpenFDALabelResponse.model_validate(response.json())
            except ValueError as exc:
                last_error = exc
                logger.warning(
                    "openfda_response_parse_failure query=%s error=%s",
                    search_query,
                    exc.__class__.__name__,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                raise OpenFDAIntegrationError("openFDA response format was unexpected") from exc

        raise OpenFDAIntegrationError("openFDA request failed") from last_error

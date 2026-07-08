import httpx
import logging

from app.core.exceptions import LLMProviderError
from app.providers.base import SAFETY_MEDICINE_SYSTEM_PROMPT, BaseLLMProvider

logger = logging.getLogger("app.llm")


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def generate_response(self, prompt: str) -> str:
        return await self.generate_response_with_system(
            system_prompt=SAFETY_MEDICINE_SYSTEM_PROMPT,
            user_prompt=prompt,
        )

    async def generate_response_with_system(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise LLMProviderError("Gemini API key is not configured")
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )

        logger.info(
            "LLM API call start provider=gemini model=%s endpoint=%s",
            self.model,
            url,
        )
        logger.info(
            "LLM API call waiting provider=gemini model=%s",
            self.model,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)

        logger.info(
            "LLM API call completed provider=gemini model=%s status=%s",
            self.model,
            response.status_code,
        )

        if response.status_code >= 400:
            raise LLMProviderError(f"Gemini request failed: {response.text}")

        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("Gemini response format was unexpected") from exc

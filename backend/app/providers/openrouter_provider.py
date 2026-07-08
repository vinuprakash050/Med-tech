import httpx
import logging

from app.core.exceptions import LLMProviderError
from app.providers.base import SAFETY_MEDICINE_SYSTEM_PROMPT, BaseLLMProvider

logger = logging.getLogger("app.llm")


class OpenRouterProvider(BaseLLMProvider):
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
            raise LLMProviderError("OpenRouter API key is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        }

        logger.info(
            "LLM API call start provider=openrouter model=%s endpoint=%s",
            self.model,
            endpoint,
        )
        logger.info(
            "LLM API call waiting provider=openrouter model=%s",
            self.model,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
            )

        logger.info(
            "LLM API call completed provider=openrouter model=%s status=%s",
            self.model,
            response.status_code,
        )

        if response.status_code >= 400:
            raise LLMProviderError(f"OpenRouter request failed: {response.text}")

        data = response.json()
        try:
            message = data["choices"][0]["message"]["content"]
            if isinstance(message, list):
                return "".join([part.get("text", "") for part in message]).strip()
            return str(message).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("OpenRouter response format was unexpected") from exc

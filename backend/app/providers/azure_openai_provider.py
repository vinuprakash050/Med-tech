import base64
import httpx
import logging

from app.core.exceptions import LLMProviderError
from app.providers.base import SAFETY_MEDICINE_SYSTEM_PROMPT, BaseLLMProvider

logger = logging.getLogger("app.llm")


class AzureOpenAIProvider(BaseLLMProvider):
    """
    Provider for Azure-hosted OpenAI deployments accessed via an APIM gateway.

    Supports both text and vision (image) inputs.

    Configure via .env:
        LLM_PROVIDER=azure_openai
        AZURE_OPENAI_API_KEY=<your-key>
        AZURE_OPENAI_ENDPOINT=https://.../gpt54/deployments/gpt-5.4/chat/completions?api-version=...
        AZURE_OPENAI_VISION_ENDPOINT=https://.../gpt54/deployments/gpt-5.4/chat/completions?api-version=...
    """

    def __init__(
        self,
        api_key: str | None,
        endpoint: str | None,
        vision_endpoint: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.endpoint = endpoint
        # Vision endpoint — falls back to main endpoint if not set separately
        self.vision_endpoint = vision_endpoint or endpoint

    @property
    def supports_vision(self) -> bool:
        return bool(self.vision_endpoint and self.api_key)

    async def generate_response(self, prompt: str) -> str:
        return await self.generate_response_with_system(
            system_prompt=SAFETY_MEDICINE_SYSTEM_PROMPT,
            user_prompt=prompt,
        )

    async def generate_response_with_system(
        self, system_prompt: str, user_prompt: str
    ) -> str:
        if not self.api_key:
            raise LLMProviderError("Azure OpenAI API key is not configured")
        if not self.endpoint:
            raise LLMProviderError("Azure OpenAI endpoint is not configured")

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_completion_tokens": 1500,
        }
        return await self._post(self.endpoint, payload)

    async def generate_response_with_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """
        Send an image + text prompt to the GPT-5.4 Vision (Local Image) endpoint.
        Image is resized to max 1120px and base64-encoded to reduce payload size.
        """
        if not self.api_key:
            raise LLMProviderError("Azure OpenAI API key is not configured")
        if not self.vision_endpoint:
            raise LLMProviderError("Azure OpenAI vision endpoint is not configured")

        # Resize image to reduce base64 payload — vision models don't need
        # full-resolution images; 1120px long edge is plenty for text reading
        optimized_bytes = _resize_image_for_vision(image_bytes, max_long_edge=1120)
        b64_image = base64.b64encode(optimized_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64_image}"

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": "high"},
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
            "temperature": 0.1,
            "max_completion_tokens": 800,
        }
        return await self._post(self.vision_endpoint, payload)

    async def _post(self, endpoint: str, payload: dict) -> str:
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        logger.info("LLM API call start provider=azure_openai endpoint=%s", endpoint)
        logger.info("LLM API call waiting provider=azure_openai")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, json=payload)

        logger.info(
            "LLM API call completed provider=azure_openai status=%s",
            response.status_code,
        )

        if response.status_code >= 400:
            raise LLMProviderError(f"Azure OpenAI request failed: {response.text}")

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("Azure OpenAI response format was unexpected") from exc


# ── Image resize helper ───────────────────────────────────────────────────────

def _resize_image_for_vision(image_bytes: bytes, max_long_edge: int = 1120) -> bytes:
    """
    Resize image so the longest edge is at most max_long_edge pixels.
    Returns JPEG bytes. Falls back to original bytes on any error.
    Vision models don't need full-resolution images — 1120px is enough
    to read printed and handwritten text clearly, and cuts payload size
    by 60-80% for typical phone photos.
    """
    try:
        import io
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        long_edge = max(w, h)

        if long_edge <= max_long_edge:
            # Already small enough — just re-encode as JPEG to normalise format
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88, optimize=True)
            return buf.getvalue()

        scale = max_long_edge / long_edge
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        img = img.resize((new_w, new_h), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        resized = buf.getvalue()
        logger.info(
            "vision_image_resize original=%dKB resized=%dKB dims=%dx%d",
            len(image_bytes) // 1024,
            len(resized) // 1024,
            new_w,
            new_h,
        )
        return resized
    except Exception as exc:
        logger.warning("vision_image_resize_failed error=%s using_original", exc)
        return image_bytes

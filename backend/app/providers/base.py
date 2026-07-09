from abc import ABC, abstractmethod

SAFETY_MEDICINE_SYSTEM_PROMPT = (
    "Use only the supplied medicine data. Do not diagnose, prescribe, "
    "recommend stopping medicine, or suggest treatment. Keep the response "
    "concise, factual, and informational only."
)


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        raise NotImplementedError

    async def generate_response_with_system(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate a response using an explicit system prompt.
        Default implementation concatenates system + user prompt and delegates to
        generate_response. Subclasses should override to use native system prompt support.
        """
        combined = f"{system_prompt}\n\n{user_prompt}"
        return await self.generate_response(combined)

    async def generate_response_with_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """
        Generate a response that includes an image in the user message.
        Default implementation ignores the image and falls back to text-only.
        Subclasses that support vision should override this method.
        """
        return await self.generate_response_with_system(system_prompt, user_prompt)

    @property
    def supports_vision(self) -> bool:
        """Return True if this provider can process image inputs natively."""
        return False

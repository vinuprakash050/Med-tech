import logging

from app.providers.base import BaseLLMProvider

logger = logging.getLogger("app.llm")


class MockLLMProvider(BaseLLMProvider):
    """
    No-op LLM provider used when no real provider is configured.
    The insights agent checks `is_mock` and builds insights directly
    from DB fields instead of calling this provider.
    """

    is_mock = True

    async def generate_response(self, prompt: str) -> str:
        logger.info("LLM API call start provider=mock model=mock-model endpoint=none")
        logger.info("LLM API call waiting provider=mock model=mock-model")
        if "No lower-priced alternatives" in prompt:
            result = (
                "No cheaper medicine with the same salt composition and dosage was found "
                "in the database, so no safe equivalent recommendation can be made."
            )
        else:
            result = (
                "These alternatives have the same salt composition and dosage as the requested "
                "medicine. They were selected from approved medicines in the database and sorted "
                "to prioritize generic and lower-priced options."
            )
        logger.info("LLM API call completed provider=mock model=mock-model status=mock")
        return result

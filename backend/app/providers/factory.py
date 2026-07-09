from app.core.config import Settings
from app.providers.azure_openai_provider import AzureOpenAIProvider
from app.providers.base import BaseLLMProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.groq_provider import GroqProvider
from app.providers.mock_provider import MockLLMProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.openrouter_provider import OpenRouterProvider


def get_llm_provider(settings: Settings) -> BaseLLMProvider:
    if settings.llm_provider == "openai":
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.llm_model)
    if settings.llm_provider == "gemini":
        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.llm_model)
    if settings.llm_provider == "groq":
        return GroqProvider(api_key=settings.groq_api_key, model=settings.llm_model)
    if settings.llm_provider == "openrouter":
        return OpenRouterProvider(api_key=settings.openrouter_api_key, model=settings.llm_model)
    if settings.llm_provider == "azure_openai":
        return AzureOpenAIProvider(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            vision_endpoint=settings.azure_openai_vision_endpoint,
        )
    return MockLLMProvider()

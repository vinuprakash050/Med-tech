from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "genRx API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/medicine_db"
    )
    openfda_base_url: str = "https://api.fda.gov"
    openfda_api_key: str | None = None
    llm_provider: Literal["openai", "gemini", "groq", "openrouter", "azure_openai", "mock"] = "mock"
    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_vision_endpoint: str | None = None
    llm_model: str = "mock-model"
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        # Load project-level .env (backend/.env) instead of app/.env
        env_file=str(ROOT_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

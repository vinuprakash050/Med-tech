import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException, LLMProviderError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
        logger.warning("Application exception: %s", exc.detail)
        detail = exc.detail
        if isinstance(exc, LLMProviderError):
            detail = (
                "AI service is temporarily unavailable or has insufficient credits. "
                "Please try again in a moment."
            )
        return JSONResponse(
            status_code=int(exc.status_code),
            content={"detail": detail},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

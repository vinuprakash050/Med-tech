import logging

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    logging.basicConfig(level=settings.log_level.upper(), format=fmt)

    # Ensure the dedicated LLM logger emits at the configured level and uses
    # the same formatting/handler as the root logger. Some servers (uvicorn)
    # reconfigure logging; setting this explicitly ensures our provider logs
    # (logger name: "app.llm") are visible at runtime.
    llm_logger = logging.getLogger("app.llm")
    llm_logger.setLevel(settings.log_level.upper())
    if not llm_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        llm_logger.addHandler(handler)

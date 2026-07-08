import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.main import app
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _mask_database_url(url: str) -> str:
    # Mask password in a DSN for safe logging
    try:
        from urllib.parse import urlparse, urlunparse

        p = urlparse(url)
        if p.password:
            netloc = f"{p.username}:******@{p.hostname}"
            if p.port:
                netloc += f":{p.port}"
            masked = urlunparse((p.scheme, netloc, p.path or "", p.params or "", p.query or "", p.fragment or ""))
            return masked
    except Exception:
        pass
    return url


def run_migrations() -> None:
    project_root = Path(__file__).resolve().parent
    alembic_ini = project_root / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning("Alembic config not found at %s, skipping migrations", alembic_ini)
        return

    # Print resolved database URL (masked) for debugging environment issues
    settings = get_settings()
    logger.info("Resolved DATABASE_URL: %s", _mask_database_url(settings.database_url))

    config = Config(str(alembic_ini))
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.set_main_option("sqlalchemy.url", str(settings.database_url))
    logger.info("Running Alembic migrations from %s", alembic_ini)
    command.upgrade(config, "head")


run_migrations()


if __name__ == "__main__":
    # Start the ASGI server when run as a script. Use uvicorn directly so
    # `python run.py` will run migrations and then serve the app.
    try:
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
    except Exception:
        logger.exception("Failed to start ASGI server")

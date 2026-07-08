from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)

# SQLAlchemy compatibility: async_sessionmaker exists in newer versions.
try:
    from sqlalchemy.ext.asyncio import async_sessionmaker  # type: ignore
except ImportError:  # pragma: no cover
    async_sessionmaker = None

# Fallback for older SQLAlchemy: use sessionmaker with AsyncSession.
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()


# SQLAlchemy compatibility: older versions may not have DeclarativeBase.
try:
    from sqlalchemy.orm import DeclarativeBase  # type: ignore

    class Base(DeclarativeBase):
        pass

except ImportError:  # pragma: no cover
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()



engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# Helpful check: ensure an async DB driver is used (asyncpg for Postgres).
if "asyncpg" not in settings.database_url and settings.database_url.startswith(
    "postgresql"
):
    raise RuntimeError(
        "DATABASE_URL must use an async driver (e.g. use 'postgresql+asyncpg://')."
    )

if async_sessionmaker is not None:
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
else:
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )



async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

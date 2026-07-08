from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.vendor import router as vendor_router
from app.api.routes.medicines import list_router as medicines_list_router
from app.api.routes.medicines import router as medicine_router
from app.core.config import get_settings
from app.integrations.openfda.client import OpenFDAClient
from app.utils.logging import configure_logging
from app.utils.middleware import register_exception_handlers

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    openfda_client = OpenFDAClient(
        base_url=settings.openfda_base_url,
        api_key=settings.openfda_api_key,
    )
    app_instance.state.openfda_client = openfda_client
    try:
        yield
    finally:
        await openfda_client.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(health_router)
app.include_router(medicine_router, prefix=settings.api_v1_prefix)
app.include_router(medicines_list_router, prefix=settings.api_v1_prefix)
app.include_router(vendor_router, prefix=settings.api_v1_prefix)

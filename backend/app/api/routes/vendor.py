from fastapi import APIRouter, HTTPException
from datetime import datetime

from app.agents.vendor_discount_agent import VendorDiscountAgent, load_vendor_medicines
from app.dto.vendor import (
    VendorDashboardResponse,
    VendorRawDashboardResponse,
    VendorRawMedicineResponse,
    VendorRawSummaryResponse,
)
from app.core.config import get_settings
from app.providers.factory import get_llm_provider
from app.providers.mock_provider import MockLLMProvider

router = APIRouter(prefix="/vendor", tags=["vendor"])


def _days_until_expiry(expiry_date: str) -> int:
    target = datetime.strptime(expiry_date, "%Y-%m-%d")
    return (target.date() - datetime.now().date()).days


def _build_raw_dashboard() -> VendorRawDashboardResponse:
    medicines = load_vendor_medicines()
    raw_medicines = [
        VendorRawMedicineResponse(**medicine.__dict__)
        for medicine in medicines
    ]
    summary = VendorRawSummaryResponse(
        medicines_tracked=len(raw_medicines),
        expiring_within_30_days=sum(1 for medicine in raw_medicines if _days_until_expiry(medicine.expiry_date) <= 30),
        total_stock=sum(medicine.stock for medicine in raw_medicines),
    )
    return VendorRawDashboardResponse(summary=summary, medicines=raw_medicines)


@router.get("/raw", response_model=VendorRawDashboardResponse, response_model_exclude_none=True)
async def get_vendor_raw_dashboard() -> VendorRawDashboardResponse:
    return _build_raw_dashboard()


@router.get("/dashboard", response_model=VendorDashboardResponse, response_model_exclude_none=True)
async def get_vendor_dashboard() -> VendorDashboardResponse:
    settings = get_settings()
    provider = get_llm_provider(settings)
    if isinstance(provider, MockLLMProvider):
        raise HTTPException(
            status_code=503,
            detail="Vendor dashboard needs a configured LLM provider; mock responses are disabled.",
        )
    agent = VendorDiscountAgent(llm_provider=provider)
    return await agent.build_dashboard(load_vendor_medicines())

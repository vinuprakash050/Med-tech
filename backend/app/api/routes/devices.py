from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.agents.device_feedback_agent import (
    DeviceFeedbackAgent,
    get_feedback_for_model,
    load_device_data,
)
from app.core.config import get_settings
from app.dto.device import (
    DeviceFeedbackAnalysis,
    DeviceModelResponse,
    DeviceResponse,
    DeviceSearchResponse,
    DeviceSearchResultItem,
)
from app.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _all_devices() -> list[DeviceResponse]:
    data = load_device_data()
    return [
        DeviceResponse(
            id=d["id"],
            name=d["name"],
            category=d["category"],
            search_keywords=d["search_keywords"],
            models=[DeviceModelResponse(**m) for m in d["models"]],
        )
        for d in data.get("devices", [])
    ]


def _query_matches(device: DeviceResponse, q: str) -> bool:
    """Return True if the search query matches this device category."""
    q_lower = q.lower().strip()
    if not q_lower:
        return True
    # Match against keywords list and device name
    return any(q_lower in kw.lower() for kw in device.search_keywords) or \
           q_lower in device.name.lower()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=DeviceSearchResponse)
async def search_devices(
    q: str = Query(default="", description="Search query — e.g. 'hearing aid', 'pacemaker'"),
) -> DeviceSearchResponse:
    """
    Search medical devices by keyword.
    Returns slim DeviceSearchResultItem cards suitable for embedding in the
    main search results page alongside medicines.
    """
    devices = _all_devices()
    results: list[DeviceSearchResultItem] = []

    for device in devices:
        if not _query_matches(device, q):
            continue
        for model in device.models:
            results.append(
                DeviceSearchResultItem(
                    model_id=model.model_id,
                    device_id=device.id,
                    device_name=device.name,
                    model_name=model.model_name,
                    brand=model.brand,
                    price=model.price,
                    rating=model.rating,
                    image_icon=model.image_icon,
                    uses=model.uses,
                    unique_characteristics=model.unique_characteristics,
                )
            )

    logger.info("device_search query=%r results=%d", q, len(results))
    return DeviceSearchResponse(query=q, results=results)


@router.get("/all", response_model=list[DeviceResponse])
async def list_all_devices() -> list[DeviceResponse]:
    """
    Return the complete device catalogue (all categories and models).
    Used by the vendor devices page to render the full list before
    the AI feedback analysis is fetched.
    """
    return _all_devices()


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str) -> DeviceResponse:
    """Return a single device with all its models by device ID (e.g. 'ha-001')."""
    for device in _all_devices():
        if device.id == device_id:
            return device
    raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found.")


@router.get("/{model_id}/feedback-analysis", response_model=DeviceFeedbackAnalysis)
async def get_device_feedback_analysis(model_id: str) -> DeviceFeedbackAnalysis:
    """
    Vendor-only endpoint.
    Fetches all survey feedback for a device model, passes it to the
    DeviceFeedbackAgent, and returns an AI-generated pros/cons analysis.

    model_id examples: ha-001-m1, pm-001-m2
    """
    meta, entries = get_feedback_for_model(model_id)

    if meta is None:
        raise HTTPException(
            status_code=404,
            detail=f"No device model found with id '{model_id}'.",
        )

    settings = get_settings()
    provider = get_llm_provider(settings)

    agent = DeviceFeedbackAgent(llm_provider=provider)

    logger.info(
        "device_feedback_analysis_start model_id=%s reviews=%d provider=%s",
        model_id,
        len(entries),
        type(provider).__name__,
    )

    analysis = await agent.analyse(
        model_id=model_id,
        model_name=meta.model_name,
        brand=meta.brand,
        entries=entries,
    )

    return analysis

from __future__ import annotations

"""
Prescription API Route
======================
POST /api/v1/prescription/analyze

Accepts a multipart/form-data upload with a single image file and returns
a PrescriptionAnalysisResponse containing structured medicine data and
recommendations.

Validation
----------
- File size: max 10 MB  (also enforced inside PrescriptionOCRService)
- File type: image/jpeg, image/jpg, image/png (MIME check + extension check)
- PDF: explicitly rejected with a clear 415 error

Error handling
--------------
- OCRError          → 422 Unprocessable Entity
- ValueError        → 400 Bad Request  (size / type validation failures)
- AppException      → handled by global middleware (middleware.py)
- Unexpected errors → handled by global middleware → 500
"""

import logging
from http import HTTPStatus

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import AppException
from app.dto.prescription import PrescriptionAnalysisResponse
from app.services.prescription_analysis import (
    PrescriptionAnalysisService,
    get_prescription_analysis_service,
)
from app.services.prescription_ocr import OCRError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prescription", tags=["prescription"])

# Allowed MIME types (normalised, lower-case)
_ALLOWED_MIME = frozenset({"image/jpeg", "image/jpg", "image/png", "image/webp"})
_REJECTED_MIME = frozenset({"application/pdf", "application/x-pdf"})
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Dependency ────────────────────────────────────────────────────────────────

def _get_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> PrescriptionAnalysisService:
    openfda_client = getattr(request.app.state, "openfda_client", None)
    return get_prescription_analysis_service(
        session=session,
        openfda_client=openfda_client,
    )


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=PrescriptionAnalysisResponse,
    response_model_exclude_none=True,
    summary="Analyze a prescription image",
    description=(
        "Upload a prescription image (JPEG / PNG, max 10 MB). "
        "Returns detected medicines with alternatives and AI insights."
    ),
)
async def analyze_prescription(
    file: UploadFile = File(..., description="Prescription image (JPEG or PNG, max 10 MB)"),
    generic_preference: bool = Form(default=True, description="Prefer generic alternatives"),
    service: PrescriptionAnalysisService = Depends(_get_service),
) -> PrescriptionAnalysisResponse:
    """
    Full prescription OCR → parse → recommend pipeline.

    Steps:
    1. Validate file type and size
    2. Read image bytes
    3. Delegate to PrescriptionAnalysisService
    4. Return PrescriptionAnalysisResponse
    """
    # ── Validate MIME type ────────────────────────────────────────────────────
    content_type = (file.content_type or "").split(";")[0].strip().lower()

    if content_type in _REJECTED_MIME:
        return JSONResponse(
            status_code=int(HTTPStatus.UNSUPPORTED_MEDIA_TYPE),
            content={
                "detail": (
                    "PDF files are not supported yet. "
                    "Please upload a JPEG or PNG image of the prescription."
                )
            },
        )

    if content_type not in _ALLOWED_MIME:
        # Also accept when content_type is empty / wrong but filename hints at image
        filename = (file.filename or "").lower()
        if not any(filename.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
            return JSONResponse(
                status_code=int(HTTPStatus.UNSUPPORTED_MEDIA_TYPE),
                content={
                    "detail": (
                        f"Unsupported file type '{content_type or file.filename}'. "
                        "Please upload a JPEG or PNG image."
                    )
                },
            )
        # Allow through if the extension matches even when MIME is wrong
        if filename.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif filename.endswith(".png"):
            content_type = "image/png"
        elif filename.endswith(".webp"):
            content_type = "image/webp"

    # ── Read image bytes ──────────────────────────────────────────────────────
    image_bytes = await file.read()

    if len(image_bytes) == 0:
        return JSONResponse(
            status_code=int(HTTPStatus.BAD_REQUEST),
            content={"detail": "Uploaded file is empty."},
        )

    if len(image_bytes) > _MAX_BYTES:
        mb = len(image_bytes) / 1024 / 1024
        return JSONResponse(
            status_code=int(HTTPStatus.REQUEST_ENTITY_TOO_LARGE),
            content={
                "detail": (
                    f"File size {mb:.1f} MB exceeds the 10 MB limit. "
                    "Please compress or resize the image and try again."
                )
            },
        )

    logger.info(
        "prescription_analyze_request filename=%s content_type=%s size=%d generic_pref=%s",
        file.filename,
        content_type,
        len(image_bytes),
        generic_preference,
    )

    # ── Delegate to service ───────────────────────────────────────────────────
    try:
        result = await service.analyze(
            image_bytes=image_bytes,
            content_type=content_type,
            generic_preference=generic_preference,
        )
    except (OCRError, ValueError) as exc:
        logger.warning("prescription_analyze_ocr_error error=%s", exc)
        return JSONResponse(
            status_code=int(HTTPStatus.UNPROCESSABLE_ENTITY),
            content={"detail": str(exc)},
        )
    except AppException:
        # Let the global middleware handle this
        raise
    except Exception as exc:
        logger.exception("prescription_analyze_unexpected_error error=%s", exc)
        raise

    logger.info(
        "prescription_analyze_done medicines=%d matched=%d",
        result.summary.medicines_detected,
        result.summary.successfully_matched,
    )
    return result

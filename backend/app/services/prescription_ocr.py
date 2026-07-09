from __future__ import annotations

"""
PrescriptionOCRService
======================
Handles image preprocessing and OCR extraction.

Pipeline
--------
1. Decode raw image bytes via Pillow
2. Convert to OpenCV / NumPy format
3. Apply preprocessing (grayscale → denoise → adaptive threshold → sharpen → resize)
4. Run EasyOCR (preferred) with Tesseract as fallback
5. Return an OCRResult containing the extracted text and metadata

Dependencies (all free / offline):
    easyocr          pip install easyocr
    opencv-python    pip install opencv-python
    numpy            pip install numpy
    Pillow           pip install Pillow

Tesseract fallback requires the system binary:
    Ubuntu/Debian: sudo apt install tesseract-ocr
    macOS: brew install tesseract
    Windows: install from https://github.com/UB-Mannheim/tesseract/wiki
"""

import io
import logging
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from PIL import Image, UnidentifiedImageError

from app.dto.prescription import OCRResult

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Images are resized so the longer edge is at most this many pixels.
# Larger images slow OCR significantly without improving accuracy.
MAX_LONG_EDGE: int = 2400

# Minimum pixels on the shorter edge; very small images are upscaled.
MIN_SHORT_EDGE: int = 600

ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/jpg", "image/png", "image/webp"}
)
MAX_IMAGE_BYTES: int = 10 * 1024 * 1024  # 10 MB


# ── Lazy EasyOCR reader (loaded once per process) ─────────────────────────────

@lru_cache(maxsize=1)
def _get_easyocr_reader():  # type: ignore[return]
    """
    Import and instantiate EasyOCR reader lazily so that the main app
    starts even when easyocr is not yet installed (e.g. CI environments
    that don't run OCR).  Returns None when easyocr is unavailable.
    """
    try:
        import easyocr  # type: ignore[import]
        logger.info("ocr_engine_init engine=easyocr languages=['en']")
        # gpu=False ensures compatibility on CPU-only servers
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        logger.info("ocr_engine_ready engine=easyocr")
        return reader
    except ImportError:
        logger.warning("ocr_engine_unavailable engine=easyocr reason=not_installed falling_back=tesseract")
        return None
    except Exception as exc:
        logger.warning("ocr_engine_init_failed engine=easyocr error=%s falling_back=tesseract", exc)
        return None


# ── Custom exception ──────────────────────────────────────────────────────────

class OCRError(Exception):
    """Raised when the OCR pipeline cannot produce any text."""


# ── Image preprocessing ───────────────────────────────────────────────────────

@dataclass
class _PreprocessResult:
    image: np.ndarray
    steps_applied: list[str] = field(default_factory=list)


def _preprocess_image(pil_image: Image.Image) -> _PreprocessResult:
    """
    Apply a sequence of OpenCV transforms to improve OCR accuracy.

    Steps applied (in order):
        1. Convert to grayscale
        2. Smart resize (keep aspect ratio; max long edge 2400px, min short edge 600px)
        3. Gaussian denoise
        4. Adaptive threshold  (handles uneven lighting in scanned/photographed prescriptions)
        5. Sharpen via Laplacian kernel
    """
    import cv2  # type: ignore[import]

    steps: list[str] = []

    # 1. Grayscale
    img = np.array(pil_image.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    steps.append("grayscale")

    # 2. Resize
    h, w = gray.shape
    long_edge  = max(h, w)
    short_edge = min(h, w)

    if long_edge > MAX_LONG_EDGE:
        scale = MAX_LONG_EDGE / long_edge
        new_w = int(w * scale)
        new_h = int(h * scale)
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
        steps.append(f"resize_down_{new_w}x{new_h}")
    elif short_edge < MIN_SHORT_EDGE:
        scale = MIN_SHORT_EDGE / short_edge
        new_w = int(w * scale)
        new_h = int(h * scale)
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        steps.append(f"resize_up_{new_w}x{new_h}")

    # 3. Gaussian denoise
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    steps.append("denoise_gaussian")

    # 4. Adaptive threshold — converts to binary, handles shadow/lighting
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15,
        C=9,
    )
    steps.append("adaptive_threshold")

    # 5. Sharpen using a Laplacian-based unsharp mask
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(binary, -1, kernel)
    steps.append("sharpen")

    return _PreprocessResult(image=sharpened, steps_applied=steps)


# ── OCR engines ───────────────────────────────────────────────────────────────

def _run_easyocr(image: np.ndarray) -> str:
    """Run EasyOCR on a preprocessed NumPy image and return the joined text."""
    reader = _get_easyocr_reader()
    if reader is None:
        raise OCRError("EasyOCR reader not available")

    results = reader.readtext(image, detail=1, paragraph=False)
    # results: list of (bbox, text, confidence)
    lines = [text for (_bbox, text, conf) in results if conf >= 0.15 and text.strip()]
    return "\n".join(lines)


def _run_tesseract(image: np.ndarray) -> str:
    """
    Tesseract fallback.  Requires pytesseract + the tesseract system binary.
    Returns empty string if pytesseract is not installed.
    """
    try:
        import pytesseract  # type: ignore[import]
        from PIL import Image as PILImage  # already available

        pil_img = PILImage.fromarray(image)
        text = pytesseract.image_to_string(pil_img, config="--psm 6")
        return text.strip()
    except ImportError:
        logger.warning("ocr_fallback_unavailable engine=tesseract reason=pytesseract_not_installed")
        return ""
    except Exception as exc:
        logger.warning("ocr_fallback_failed engine=tesseract error=%s", exc)
        return ""


# ── Main service ──────────────────────────────────────────────────────────────

class PrescriptionOCRService:
    """
    Stateless service that converts raw image bytes into an OCRResult.

    Usage::

        service = PrescriptionOCRService()
        result  = await service.extract(image_bytes, content_type="image/jpeg")
    """

    async def extract(
        self,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
    ) -> OCRResult:
        """
        Full OCR pipeline: validate → preprocess → EasyOCR → (Tesseract fallback).

        Parameters
        ----------
        image_bytes:
            Raw bytes from the uploaded file.
        content_type:
            MIME type of the uploaded file.  Used for early validation only.

        Returns
        -------
        OCRResult
            Contains `raw_text` (the extracted text) and metadata.

        Raises
        ------
        OCRError
            When the image cannot be decoded or no text could be extracted.
        ValueError
            When the content type or file size is invalid.
        """
        self._validate(image_bytes, content_type)

        # Decode image
        pil_image = self._decode_image(image_bytes)

        # Preprocessing
        logger.info("ocr_preprocessing_start size=%d content_type=%s", len(image_bytes), content_type)
        prep = _preprocess_image(pil_image)
        logger.info("ocr_preprocessing_done steps=%s", prep.steps_applied)

        # EasyOCR (primary)
        raw_text = ""
        engine_used = "none"
        try:
            raw_text = _run_easyocr(prep.image)
            if raw_text.strip():
                engine_used = "easyocr"
                logger.info(
                    "ocr_extraction_complete engine=easyocr chars=%d",
                    len(raw_text),
                )
        except OCRError as exc:
            logger.info("ocr_primary_failed reason=%s", exc)

        # Tesseract fallback
        if not raw_text.strip():
            logger.info("ocr_fallback_attempt engine=tesseract")
            raw_text = _run_tesseract(prep.image)
            if raw_text.strip():
                engine_used = "tesseract"
                logger.info(
                    "ocr_extraction_complete engine=tesseract chars=%d",
                    len(raw_text),
                )

        if not raw_text.strip():
            raise OCRError(
                "Could not extract any text from the prescription image. "
                "Please ensure the image is clear and well-lit."
            )

        word_count = len(raw_text.split())
        logger.info(
            "ocr_done engine=%s words=%d preprocessing=%s",
            engine_used,
            word_count,
            ",".join(prep.steps_applied),
        )

        return OCRResult(
            raw_text=raw_text,
            word_count=word_count,
            preprocessing_applied=prep.steps_applied,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _validate(image_bytes: bytes, content_type: str) -> None:
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValueError(
                f"Image size {len(image_bytes) / 1024 / 1024:.1f} MB exceeds the 10 MB limit."
            )
        # Normalise content type (strip charset params etc.)
        mime = content_type.split(";")[0].strip().lower()
        if mime not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                f"Unsupported file type '{mime}'. "
                "Please upload a JPEG or PNG image."
            )

    @staticmethod
    def _decode_image(image_bytes: bytes) -> Image.Image:
        try:
            return Image.open(io.BytesIO(image_bytes))
        except UnidentifiedImageError as exc:
            raise OCRError(
                "Could not decode the uploaded image. "
                "Please upload a valid JPEG or PNG file."
            ) from exc

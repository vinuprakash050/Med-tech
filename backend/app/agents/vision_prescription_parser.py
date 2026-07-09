from __future__ import annotations

"""
VisionPrescriptionParser
========================
Uses a vision-capable LLM (GPT-5.4 Vision) to extract medicines directly
from the prescription image — bypassing EasyOCR entirely.

This is significantly more accurate for:
- Handwritten prescriptions
- Prescriptions with mixed print + handwriting
- Noisy / tilted / low-light images

Falls back to the text-based PrescriptionParserAgent when the provider
does not support vision.
"""

import json
import logging
import re

from app.agents.prescription_parser import (
    PrescriptionParseResult,
    PrescriptionParserAgent,
    _heuristic_extract,
)
from app.dto.prescription import ParsedMedicine
from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# ── Vision-specific system prompt ─────────────────────────────────────────────
# Shorter than the text prompt because the model sees the image directly —
# no need to describe OCR error patterns.

VISION_SYSTEM_PROMPT = """\
You are a medical prescription reader. Look at this prescription image and extract only the medicines prescribed by the doctor.

OUTPUT: JSON only, no markdown, no explanation.
SCHEMA: {"patient_name":null,"doctor":null,"date":null,"medicines":[{"medicine_name":"","dosage":null,"dosage_form":null,"frequency":null,"duration":null,"confidence":0.0}]}

INCLUDE lines where the doctor wrote a medicine — look for:
- Dosage form prefix: T. Tab. Cap. Syr. Syp. Inj. Ol. Cr. Oint. (tablet/capsule/syrup/injection/oil/cream)
- Dosage amounts: mg, ml, mcg
- Frequency: 1-0-1, BD, TID, OD, SOS, once daily, twice daily

EXCLUDE everything else: clinic/hospital header, patient name, doctor name/credentials,
appointment date, clinical notes, complaints, procedures (K-wire removal, regional block, C-arm),
admit instructions, followup, physiotherapy, X-ray, diagnostics, pharmacy, footer, addresses.

Fix common handwriting misreads: "07." or "01." at line start = "Ol." (oil drops).
For brand names, use the name as written by the doctor.
If no medicines found: {"patient_name":null,"doctor":null,"date":null,"medicines":[]}
"""

VISION_USER_PROMPT = "Extract the prescribed medicines from this prescription image. Return JSON only."


class VisionPrescriptionParser:
    """
    Primary prescription parser when a vision-capable provider is available.

    Usage::

        parser = VisionPrescriptionParser(llm_provider)
        result = await parser.parse_image(image_bytes, content_type)
    """

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider
        # Text fallback for when vision is unavailable
        self._text_parser = PrescriptionParserAgent(llm_provider)

    async def parse_image(
        self,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
        ocr_text_fallback: str | None = None,
    ) -> PrescriptionParseResult:
        """
        Parse a prescription image directly using vision LLM.

        Parameters
        ----------
        image_bytes:
            Raw bytes of the prescription image (JPEG / PNG).
        content_type:
            MIME type of the image.
        ocr_text_fallback:
            OCR text to use if vision is unavailable.

        Returns
        -------
        PrescriptionParseResult
        """
        if not self.llm_provider.supports_vision:
            logger.info(
                "vision_parser_skip reason=provider_no_vision provider=%s — using text fallback",
                type(self.llm_provider).__name__,
            )
            if ocr_text_fallback:
                return await self._text_parser.parse(ocr_text_fallback)
            return PrescriptionParseResult(
                patient_name=None, doctor=None, date=None, medicines=[]
            )

        logger.info(
            "vision_parser_start provider=%s size=%d",
            type(self.llm_provider).__name__,
            len(image_bytes),
        )

        try:
            raw_response = await self.llm_provider.generate_response_with_image(
                system_prompt=VISION_SYSTEM_PROMPT,
                user_prompt=VISION_USER_PROMPT,
                image_bytes=image_bytes,
                content_type=content_type,
            )
            logger.info("vision_parser_llm_done chars=%d", len(raw_response))
        except Exception as exc:
            logger.warning(
                "vision_parser_llm_failed error=%s — falling back to OCR text",
                exc,
            )
            if ocr_text_fallback:
                return await self._text_parser.parse(ocr_text_fallback)
            return PrescriptionParseResult(
                patient_name=None, doctor=None, date=None,
                medicines=[], used_fallback=True,
            )

        return self._parse_response(raw_response, ocr_text_fallback)

    def _parse_response(
        self,
        raw_response: str,
        ocr_fallback_text: str | None,
    ) -> PrescriptionParseResult:
        """Decode the JSON response from the vision LLM."""
        try:
            clean = _extract_json(raw_response)
            data = json.loads(clean)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "vision_parser_json_failed error=%s — using heuristic on OCR text", exc
            )
            medicines = _heuristic_extract(ocr_fallback_text or "")
            return PrescriptionParseResult(
                patient_name=None, doctor=None, date=None,
                medicines=medicines, used_fallback=bool(medicines),
            )

        raw_medicines = data.get("medicines") or []
        if not isinstance(raw_medicines, list):
            raw_medicines = []

        medicines: list[ParsedMedicine] = []
        for item in raw_medicines:
            if not isinstance(item, dict):
                continue
            name = str(item.get("medicine_name") or "").strip()
            if not name:
                continue
            try:
                conf = max(0.0, min(1.0, float(item.get("confidence") or 0.7)))
            except (TypeError, ValueError):
                conf = 0.7

            medicines.append(
                ParsedMedicine(
                    medicine_name=name,
                    dosage=_str_or_none(item.get("dosage")),
                    dosage_form=_str_or_none(item.get("dosage_form")),
                    frequency=_str_or_none(item.get("frequency")),
                    duration=_str_or_none(item.get("duration")),
                    confidence=conf,
                )
            )

        logger.info("vision_parser_done medicines=%d", len(medicines))
        return PrescriptionParseResult(
            patient_name=_str_or_none(data.get("patient_name")),
            doctor=_str_or_none(data.get("doctor")),
            date=_str_or_none(data.get("date")),
            medicines=medicines,
            used_fallback=False,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> str:
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    if fenced:
        return fenced.group(1).strip()
    brace = re.search(r"\{[\s\S]+\}", raw)
    if brace:
        return brace.group(0).strip()
    return raw.strip()


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None

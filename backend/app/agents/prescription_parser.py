from __future__ import annotations

"""
PrescriptionParserAgent
=======================
Converts raw OCR text into a structured list of medicines using the
existing LLM provider abstraction.

When the LLM is not available (mock mode) or fails, the agent falls
back to a heuristic regex-based extractor so the pipeline never returns
an empty result just because the LLM is down.
"""

import json
import logging
import re
from dataclasses import dataclass

from app.dto.prescription import ParsedMedicine
from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

PARSER_SYSTEM_PROMPT = """\
Extract prescribed medicines from OCR text of an Indian doctor's prescription.

OUTPUT: JSON only, no markdown, no explanation.
SCHEMA:
{"patient_name":null,"doctor":null,"date":null,"medicines":[{"medicine_name":"","dosage":null,"dosage_form":null,"frequency":null,"duration":null,"confidence":0.0}]}

INCLUDE only lines where the doctor wrote a medicine. Signals:
- Starts with T. Tab. Cap. Syr. Syp. Inj. Ol. Cr. Oint. Susp. Gel. (dosage-form prefix)
- Contains mg/ml/mcg or frequency like 1-0-1 BD TID OD SOS

EXCLUDE everything else: clinic/hospital name, patient name, doctor name/credentials,
appointment date, complaints, clinical notes, procedure notes (K-wire, regional block,
C-arm, admit, followup), address, phone, footer, X-ray, diagnostics, physiotherapy.

OCR errors to fix: "07." → "Ol.", "Ig" at line start is Rx symbol (skip it),
split words like "Ga roll" → "Garoll", "Neu min" → "Neumin".

If genuinely no medicines found, return: {"patient_name":null,"doctor":null,"date":null,"medicines":[]}
"""


# ── Fallback heuristic extractor ──────────────────────────────────────────────

# Dosage form prefixes that reliably indicate a medicine line in Indian prescriptions
# T. = tablet, Cap = capsule, Syr = syrup, Inj = injection, Ol = oil/drops,
# Cr = cream, Oint = ointment, Tab = tablet, Susp = suspension, Gel = gel
_DOSAGE_FORM_PREFIX_RE = re.compile(
    r"""
    ^\s*
    (?:T\.|Tab\.?|Cap\.?|Caps\.?|Syr\.?|Syp\.?|Inj\.?|Ol\.?|Cr\.?|Oint\.?|
       Susp\.?|Gel\.?|Drop\.?|Drp\.?|Soln\.?|Pwd\.?)
    \s*
    ([A-Za-z0-9][A-Za-z0-9\s\-\+\.]{2,40})  # medicine name after prefix
    """,
    re.VERBOSE | re.MULTILINE | re.IGNORECASE,
)

# Lines that contain a dosage/frequency marker (e.g. "500mg", "1-0-1", "BD", "TID")
_DOSAGE_MARKER_RE = re.compile(
    r"""
    ^\s*
    (?:[\d]+[\.\)]\s*)?                       # optional "1." prefix
    ([A-Z][A-Za-z0-9\-\+\s]{2,40})           # medicine name candidate
    \s+
    (?:
        \d+\s*(?:mg|mcg|ml|g|iu|%)           # dosage amount
        | \d+[-/]\d+[-/]\d+                   # frequency like 1-0-1
        | \b(?:BD|TID|OD|QID|SOS|PRN|HS|AC|PC|STAT)\b  # frequency abbreviation
    )
    """,
    re.VERBOSE | re.MULTILINE | re.IGNORECASE,
)

# Words / patterns that are NEVER medicine names
_STOP_WORDS = frozenset(
    {
        "name", "patient", "doctor", "dr", "date", "age", "sex", "diagnosis",
        "rx", "prescription", "hospital", "clinic", "address", "phone", "tel",
        "signature", "ref", "advice", "follow", "review", "next", "visit",
        "apply", "take", "use", "morning", "evening", "night", "daily", "times",
        "days", "weeks", "months", "before", "after", "meals", "food", "water",
        "the", "and", "for", "with", "without", "male", "female", "years",
        "appointment", "generated", "page", "complaints", "notes", "clinical",
        "advanced", "orthopedics", "sports", "medicine", "multispeciality",
        "physiotherapy", "xray", "x-ray", "diagnostics", "pharmacy",
        "followup", "admit", "block", "regional", "removal", "wire",
    }
)

# Patterns that strongly indicate a non-medicine line
_NON_MEDICINE_PATTERNS = re.compile(
    r"""
    (?:
        \b(?:clinic|hospital|pharmacy|diagnostic|laboratory|lab|centre|center)\b
        | \b(?:mbbs|ms|md|phd|bds|mch|ortho|regNo|tsmc)\b
        | \b(?:appointment|generated\s+on|page\s+\d)\b
        | \b(?:floor|above|bank|road|street|nagar|hyderabad|delhi|mumbai)\b
        | @|www\.|\.com|WhatsApp|\d{10}
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _heuristic_extract(raw_text: str) -> list[ParsedMedicine]:
    """
    Best-effort extraction when the LLM is unavailable.

    Only extracts lines that have an explicit dosage-form prefix (T., Cap., Syr., etc.)
    OR a clear dosage/frequency marker. This prevents clinic headers, patient names,
    and doctor credentials from being treated as medicines.
    """
    medicines: list[ParsedMedicine] = []
    seen: set[str] = set()

    def _add_candidate(name: str, dosage: str | None) -> None:
        name = name.strip()
        # Skip if matches non-medicine patterns
        if _NON_MEDICINE_PATTERNS.search(name):
            return
        first_word = name.split()[0].lower().rstrip('.')
        if first_word in _STOP_WORDS:
            return
        if len(name) < 3 or len(name) > 50:
            return
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        medicines.append(
            ParsedMedicine(
                medicine_name=name,
                dosage=dosage,
                confidence=0.45,
            )
        )

    # Pass 1: lines with explicit dosage-form prefix (highest confidence)
    for match in _DOSAGE_FORM_PREFIX_RE.finditer(raw_text):
        _add_candidate(match.group(1), None)

    # Pass 2: lines with dosage/frequency markers (only if pass 1 found nothing)
    if not medicines:
        for match in _DOSAGE_MARKER_RE.finditer(raw_text):
            _add_candidate(match.group(1), None)

    return medicines[:15]  # cap at 15 to avoid noise


# ── Dataclass for full parsed output ─────────────────────────────────────────

@dataclass
class PrescriptionParseResult:
    patient_name: str | None
    doctor: str | None
    date: str | None
    medicines: list[ParsedMedicine]
    used_fallback: bool = False


# ── Agent ─────────────────────────────────────────────────────────────────────

class PrescriptionParserAgent:
    """
    Uses the project's existing LLM provider to parse prescription OCR text.

    Falls back to heuristic extraction when:
    - The provider is in mock mode (is_mock = True)
    - The LLM call fails
    - The JSON response cannot be decoded
    """

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    async def parse(self, raw_text: str) -> PrescriptionParseResult:
        """
        Parse OCR text into structured medicine entries.

        Parameters
        ----------
        raw_text:
            The raw text produced by PrescriptionOCRService.

        Returns
        -------
        PrescriptionParseResult
            Structured output with patient info and medicine list.
        """
        if not raw_text or not raw_text.strip():
            logger.warning("prescription_parser_empty_input")
            return PrescriptionParseResult(
                patient_name=None,
                doctor=None,
                date=None,
                medicines=[],
            )

        # Skip LLM call for mock provider — use heuristics instead
        if getattr(self.llm_provider, "is_mock", False):
            logger.info("prescription_parser_using_fallback reason=mock_provider")
            medicines = _heuristic_extract(raw_text)
            return PrescriptionParseResult(
                patient_name=None,
                doctor=None,
                date=None,
                medicines=medicines,
                used_fallback=True,
            )

        # LLM call
        user_prompt = self._build_user_prompt(raw_text)
        llm_logger = logging.getLogger("app.llm")
        llm_logger.info(
            "PrescriptionParserAgent LLM call start provider=%s model=%s",
            type(self.llm_provider).__name__,
            getattr(self.llm_provider, "model", "unknown"),
        )

        try:
            raw_response = await self.llm_provider.generate_response_with_system(
                system_prompt=PARSER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            llm_logger.info("PrescriptionParserAgent LLM call completed provider=%s", type(self.llm_provider).__name__)
        except Exception as exc:
            llm_logger.warning(
                "PrescriptionParserAgent LLM call failed provider=%s error=%s — using heuristic fallback",
                type(self.llm_provider).__name__,
                exc,
            )
            return PrescriptionParseResult(
                patient_name=None,
                doctor=None,
                date=None,
                medicines=_heuristic_extract(raw_text),
                used_fallback=True,
            )

        return self._parse_llm_response(raw_response, raw_text)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _prefilter_ocr(raw_text: str) -> str:
        """
        Strip lines that are clearly not medicine-related before sending to LLM.
        Reduces token usage and prevents the LLM from getting confused by
        clinic headers, patient info, and footer noise.
        """
        # Patterns that identify non-medicine lines
        noise_line = re.compile(
            r"""
            (?:
                \b(?:clinic|hospital|pharmacy|diagnostic|laboratory|diagnostics|
                   physiotherapy|orthopaed|sports\s+medicine|multispeciality|
                   x[\s\-]?ray)\b
                | \b(?:mbbs|ms\.?|md\.?|mch|bds|phd|regn?o|tsmc)\b
                | \b(?:appointment|generated\s+on|page\s+\d|whatsapp)\b
                | \b(?:floor|above|bank|road|street|nagar|indira|hyderabad|
                       delhi|mumbai|bangalore|chennai|kolkata)\b
                | @[\w]+|www\.|\.com
                | \d{10}                          # phone number
                | \b9000[\-\s]?\d{3}[\-\s]?\d{3}\b  # specific phone pattern
                | /kindleclinics|practo
                | \bpatient\b|\bkndi\d+\b          # patient ID
                | \bcomplaint|\bclinical\s+note|\bfollow[\s\-]?up\b
                | \badmit\b|\bregional\s+block\b|\bc[\-\s]?arm\b
                | \bk[\s\-]?wire\b|\bremoval\b
            )
            """,
            re.VERBOSE | re.IGNORECASE,
        )

        filtered_lines = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if noise_line.search(stripped):
                continue
            # Skip lines that are just a date/number
            if re.fullmatch(r'[\d\s/\-\.,:]+', stripped):
                continue
            filtered_lines.append(stripped)

        return "\n".join(filtered_lines)

    @staticmethod
    def _build_user_prompt(raw_text: str) -> str:
        # Pre-filter noise before sending to LLM — saves tokens
        filtered = PrescriptionParserAgent._prefilter_ocr(raw_text)
        # Cap at 1500 chars (filtered text is much shorter than raw)
        truncated = filtered[:1500]
        if len(filtered) > 1500:
            truncated += "\n[truncated]"
        return f"OCR TEXT:\n{truncated}\n\nJSON:"

    def _parse_llm_response(
        self, raw_response: str, original_text: str
    ) -> PrescriptionParseResult:
        """Attempt to decode the LLM JSON response, falling back on failure."""
        try:
            clean = self._extract_json(raw_response)
            data = json.loads(clean)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "prescription_parser_json_decode_failed error=%s raw_len=%d — using heuristic fallback",
                exc,
                len(raw_response),
            )
            return PrescriptionParseResult(
                patient_name=None,
                doctor=None,
                date=None,
                medicines=_heuristic_extract(original_text),
                used_fallback=True,
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
                confidence_raw = float(item.get("confidence") or 0.0)
                confidence = max(0.0, min(1.0, confidence_raw))
            except (TypeError, ValueError):
                confidence = 0.5

            medicines.append(
                ParsedMedicine(
                    medicine_name=name,
                    dosage=self._str_or_none(item.get("dosage")),
                    dosage_form=self._str_or_none(item.get("dosage_form")),
                    frequency=self._str_or_none(item.get("frequency")),
                    duration=self._str_or_none(item.get("duration")),
                    confidence=confidence,
                )
            )

        # If LLM explicitly returned empty medicines list — trust it.
        # The heuristic fallback only runs when the LLM call itself failed,
        # not when it returned a valid empty result.
        used_fallback = False

        return PrescriptionParseResult(
            patient_name=self._str_or_none(data.get("patient_name")),
            doctor=self._str_or_none(data.get("doctor")),
            date=self._str_or_none(data.get("date")),
            medicines=medicines,
            used_fallback=used_fallback,
        )

    @staticmethod
    def _extract_json(raw: str) -> str:
        """Strip markdown code fences and return the first JSON object."""
        fenced = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        if fenced:
            return fenced.group(1).strip()
        brace = re.search(r"\{[\s\S]+\}", raw)
        if brace:
            return brace.group(0).strip()
        return raw.strip()

    @staticmethod
    def _str_or_none(value: object) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None

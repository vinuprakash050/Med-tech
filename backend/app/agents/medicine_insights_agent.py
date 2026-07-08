from __future__ import annotations

import json
import logging
import re
from decimal import Decimal

from app.dto.medicine import MedicineInsightsResponse
from app.models.medicine import Medicine
from app.prompts.medicine_insights import (
    INSIGHTS_SYSTEM_PROMPT,
    build_medicine_insights_prompt,
)
from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> str:
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    if fenced:
        return fenced.group(1).strip()
    brace = re.search(r"\{[\s\S]+\}", raw)
    if brace:
        return brace.group(0).strip()
    return raw.strip()


def _to_str_or_none(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _to_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _split_bullets(text: str | None, max_len: int = 120) -> list[str]:
    """
    Split OpenFDA-style text into clean, short bullet points.

    OpenFDA commonly embeds sub-items inline using '•', e.g.:
      "Severe liver damage may occur if you take • more than 8 tablets in 24 hours
       • with other drugs containing acetaminophen"

    Strategy:
    1. Pre-split on sentence boundaries first so "Allergy alert." doesn't bleed
       into the next clause.
    2. For each sentence-chunk, further split on inline '•' separators.
    3. Build context-aware bullets: "may occur if you take: more than 8 tablets".
    4. Truncate at max_len to avoid paragraph-length lines.
    5. Deduplicate preserving order.
    """
    if not text:
        return []

    # Normalise whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Phase 1 — split on sentence endings followed by a capital letter
    # Use a lookahead so we don't lose the capital
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)

    result: list[str] = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if "•" in sentence:
            parts = re.split(r"\s*•\s*", sentence)
            intro = parts[0].strip().rstrip(":").rstrip(",").strip()
            sub_items = [p.strip(" -\t") for p in parts[1:] if p.strip(" -\t")]

            if not sub_items:
                # No real sub-items — treat the whole thing as a single bullet
                clean = intro.strip(" -•\t")
                if clean and len(clean) > 4:
                    _add(result, clean[:max_len])
                continue

            # Decide whether the intro is a meaningful lead-in phrase
            action_lead = bool(re.search(
                r"(may occur if|may include|do not use|stop use|ask a doctor|"
                r"do not take|use only|use if|take if|contact a)",
                intro, re.I,
            ))

            if action_lead and intro and len(intro) > 4:
                # Combine lead + each sub-item into a compound bullet
                for item in sub_items:
                    combined = f"{intro}: {item}"
                    _add(result, combined[:max_len])
            else:
                # Intro is a standalone statement; add it then each sub-item
                if intro and len(intro) > 4:
                    _add(result, intro[:max_len])
                for item in sub_items:
                    if len(item) > 4:
                        _add(result, item[:max_len])
        else:
            clean = sentence.strip(" -•\t")
            if clean and len(clean) > 4:
                _add(result, clean[:max_len])

    return result


def _add(lst: list[str], item: str) -> None:
    """Append item to list only if not already present (case-insensitive)."""
    item = item.strip()
    if item and item.lower() not in {x.lower() for x in lst}:
        lst.append(item)


def _truncate_bullet(text: str, max_words: int) -> str:
    """Trim a bullet to at most max_words words."""
    words = text.split()
    return " ".join(words[:max_words]) if len(words) > max_words else text


def _build_fallback_insights(
    medicine: Medicine,
    reference_medicine: Medicine | None = None,
) -> MedicineInsightsResponse:
    """
    Build structured insights directly from DB fields (no LLM).
    Mirrors the same limits enforced by the LLM system prompt:
    - summary: 1 sentence, ≤ 20 words
    - key_uses: ≤ 5 items, ≤ 4 words each
    - safety: ≤ 4 items, ≤ 12 words each
    - who_careful: ≤ 3 items, ≤ 8 words each
    - side_effects: ≤ 4 items, ≤ 6 words each
    - emergency: ≤ 2 items
    """
    # ── Summary — first sentence only, capped at 20 words ────────────────────
    summary: str | None = None
    source = medicine.description or medicine.purpose
    if source:
        clean = re.sub(r"\s+", " ", source).strip()
        first_sentence = re.split(r"(?<=[.!?])\s+", clean)[0].strip().rstrip(".")
        words = first_sentence.split()
        summary = " ".join(words[:20])
        if summary and not summary.endswith("."):
            summary += "."

    # ── Key uses — short labels only, max 5 × 4 words ────────────────────────
    key_uses: list[str] = []
    for field in [medicine.purpose, medicine.indications]:
        for item in _split_bullets(field, max_len=60):
            short = _truncate_bullet(item, 4)
            _add(key_uses, short)
    key_uses = _dedupe_subsets(key_uses)[:5]

    # ── Safety points — max 4 × 12 words ─────────────────────────────────────
    safety: list[str] = []
    for field in [medicine.warnings, medicine.allergy_warnings, medicine.precautions]:
        for item in _split_bullets(field, max_len=100):
            short = _truncate_bullet(item, 12)
            _add(safety, short)
    safety = _dedupe_subsets(safety)[:4]

    # ── Side effects — max 4 × 6 words ───────────────────────────────────────
    side_effects: list[str] = []
    for field in [medicine.common_side_effects, medicine.adverse_reactions]:
        for item in _split_bullets(field, max_len=60):
            short = _truncate_bullet(item, 6)
            _add(side_effects, short)
    side_effects = _dedupe_subsets(side_effects)[:4]

    # ── Who should be careful — max 3 × 8 words ──────────────────────────────
    careful_keywords = [
        "liver", "kidney", "pregnan", "breastfeed", "alcohol", "allergy",
        "asthma", "diabetes", "heart", "blood pressure", "seizure", "elderly",
        "child", "renal", "hepatic", "interaction", "warfarin", "disease",
    ]
    who_careful = [
        _truncate_bullet(s, 8)
        for s in safety
        if any(kw in s.lower() for kw in careful_keywords)
    ][:3]

    # ── Pregnancy ─────────────────────────────────────────────────────────────
    pregnancy_kw = ["pregnan", "breastfeed", "breast-feed", "lactat", "nurs"]
    pregnancy = next(
        (s for s in safety if any(kw in s.lower() for kw in pregnancy_kw)),
        None,
    )

    # ── Emergency warnings — max 2 items ─────────────────────────────────────
    emergency_kw = ["overdose", "poison control", "seek medical help", "emergency",
                    "call 911", "critical", "immediately"]
    emergency = [
        _truncate_bullet(s, 12)
        for s in safety
        if any(kw in s.lower() for kw in emergency_kw)
    ][:2]

    # ── Why this generic ──────────────────────────────────────────────────────
    why_generic: str | None = None
    if medicine.is_generic:
        frags: list[str] = []
        if medicine.salt_composition:
            frags.append(f"Same active ingredient ({medicine.salt_composition}).")
        if reference_medicine:
            try:
                if Decimal(reference_medicine.price) > Decimal(medicine.price):
                    diff = Decimal(reference_medicine.price) - Decimal(medicine.price)
                    frags.append(f"₹{diff:.0f} cheaper than the reference.")
            except Exception:
                pass
        why_generic = " ".join(frags) or None

    return MedicineInsightsResponse(
        summary=summary,
        key_uses=key_uses,
        important_safety_points=safety,
        who_should_be_careful=who_careful,
        possible_side_effects=side_effects,
        pregnancy_breastfeeding=pregnancy,
        emergency_warnings=emergency,
        why_this_generic=why_generic,
    )


def _dedupe_subsets(items: list[str]) -> list[str]:
    """Remove items that are a substring of another item in the list."""
    result: list[str] = []
    lower_items = [i.lower() for i in items]
    for i, item in enumerate(items):
        dominated = any(
            i != j and lower_items[i] in lower_items[j]
            for j in range(len(items))
        )
        if not dominated:
            result.append(item)
    return result


class MedicineInsightsAgent:
    """
    AI-powered Medicine Insights Agent.

    When a real LLM is configured: sends medicine label data to the LLM and
    returns the structured JSON response.

    When running in mock mode (no LLM key): builds a useful response directly
    from whatever DB fields are available — never invents facts.
    """

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    async def build(
        self,
        medicine: Medicine,
        reference_medicine: Medicine | None = None,
    ) -> MedicineInsightsResponse:
        # If the provider is mock/no-op, skip the LLM call entirely and
        # build insights from the actual DB fields.
        if getattr(self.llm_provider, "is_mock", False):
            logger.info("MedicineInsightsAgent using fallback (mock provider) for '%s'", medicine.name)
            return _build_fallback_insights(medicine, reference_medicine)

        prompt = build_medicine_insights_prompt(medicine)
        try:
            llm_logger = logging.getLogger("app.llm")
            llm_logger.info(
                "MedicineInsightsAgent LLM call start provider=%s model=%s medicine=%s",
                type(self.llm_provider).__name__,
                getattr(self.llm_provider, "model", "unknown"),
                medicine.name,
            )
            llm_logger.info("MedicineInsightsAgent LLM call waiting provider=%s", type(self.llm_provider).__name__)

            raw = await self.llm_provider.generate_response_with_system(
                system_prompt=INSIGHTS_SYSTEM_PROMPT,
                user_prompt=prompt,
            )
            llm_logger.info("MedicineInsightsAgent LLM call completed provider=%s medicine=%s", type(self.llm_provider).__name__, medicine.name)
        except Exception as exc:
            logger.warning(
                "MedicineInsightsAgent LLM call failed for '%s': %s — using fallback",
                medicine.name, exc,
            )
            logging.getLogger("app.llm").warning("MedicineInsightsAgent LLM call exception provider=%s medicine=%s: %s", type(self.llm_provider).__name__, medicine.name, exc)
            return _build_fallback_insights(medicine, reference_medicine)

        result = self._parse_response(raw, medicine.name)

        # If the LLM returned an empty/useless response, fall back to DB fields
        has_content = any([
            result.summary,
            result.key_uses,
            result.important_safety_points,
            result.possible_side_effects,
        ])
        if not has_content:
            logger.info("MedicineInsightsAgent LLM returned no meaningful content for '%s' — using fallback", medicine.name)
            return _build_fallback_insights(medicine, reference_medicine)

        return result

    def _parse_response(self, raw: str, medicine_name: str) -> MedicineInsightsResponse:
        try:
            clean = _extract_json(raw)
            data = json.loads(clean)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "MedicineInsightsAgent failed to parse JSON for '%s': %s | raw=%r",
                medicine_name, exc, raw[:500],
            )
            return MedicineInsightsResponse()

        def cap_list(items: list[str], max_items: int, max_words: int) -> list[str]:
            return [_truncate_bullet(i, max_words) for i in items[:max_items]]

        # Enforce the same limits as the system prompt, even if the LLM ignores them
        summary_raw = _to_str_or_none(data.get("medicine_summary"))
        if summary_raw:
            words = summary_raw.split()
            summary_raw = " ".join(words[:20])

        return MedicineInsightsResponse(
            summary=summary_raw,
            key_uses=cap_list(_to_list(data.get("key_uses")), 5, 4),
            important_safety_points=cap_list(_to_list(data.get("important_safety_points")), 4, 12),
            who_should_be_careful=cap_list(_to_list(data.get("who_should_be_careful")), 3, 8),
            possible_side_effects=cap_list(_to_list(data.get("possible_side_effects")), 4, 6),
            pregnancy_breastfeeding=_to_str_or_none(data.get("pregnancy_breastfeeding")),
            emergency_warnings=cap_list(_to_list(data.get("emergency_warnings")), 2, 12),
            why_this_generic=_to_str_or_none(data.get("why_this_generic")),
        )

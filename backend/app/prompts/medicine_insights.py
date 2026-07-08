from __future__ import annotations

import json

from app.models.medicine import Medicine


def _collect_medicine_data(medicine: Medicine) -> dict:
    """
    Serialise only the fields that are factual source-of-truth data from OpenFDA.
    Trims each text field to 400 chars max to prevent prompt bloat.
    """
    def trim(value: str | None, limit: int = 400) -> str | None:
        if not value:
            return None
        value = " ".join(value.split())   # collapse whitespace
        return value[:limit] + "…" if len(value) > limit else value

    return {
        "name": medicine.name,
        "salt_composition": medicine.salt_composition,
        "dosage": medicine.dosage,
        "dosage_form": medicine.dosage_form,
        "generic_name": medicine.generic_name,
        "active_ingredients": trim(medicine.active_ingredients, 200),
        "description": trim(medicine.description, 400),
        "indications": trim(medicine.indications, 400),
        "purpose": trim(medicine.purpose, 300),
        "warnings": trim(medicine.warnings, 500),
        "precautions": trim(medicine.precautions, 400),
        "allergy_warnings": trim(medicine.allergy_warnings, 300),
        "adverse_reactions": trim(medicine.adverse_reactions, 300),
        "common_side_effects": trim(medicine.common_side_effects, 300),
        "is_generic": medicine.is_generic,
        "price": str(medicine.price),
    }


INSIGHTS_SYSTEM_PROMPT = """\
You are a medicine label summariser. Convert raw medicine label data into \
short, scannable structured insights for a general audience.

RULES (follow exactly):
1. Use ONLY the data in the input JSON. Never add external knowledge.
2. If a field is null/missing, omit that output field (return null or []).
3. Do not diagnose, prescribe, or recommend stopping any medicine.
4. Return ONLY valid JSON — no markdown, no prose outside the JSON.

OUTPUT FORMAT:
{
  "medicine_summary": "<ONE sentence: what is this medicine and what is it for. Max 20 words.>",
  "key_uses": ["<3 words max per item>", ...],
  "important_safety_points": ["<max 10 words per item>", ...],
  "who_should_be_careful": ["<max 8 words per item>", ...],
  "possible_side_effects": ["<max 6 words per item>", ...],
  "pregnancy_breastfeeding": "<one short sentence or null>",
  "emergency_warnings": ["<max 10 words per item>", ...],
  "why_this_generic": "<one sentence only if is_generic is true, else null>"
}

LIMITS (hard):
- medicine_summary: max 20 words, 1 sentence
- key_uses: max 5 items, each ≤ 4 words (e.g. "Fever", "Headache relief", "Muscle pain")
- important_safety_points: max 4 items, each ≤ 12 words
- who_should_be_careful: max 3 items, each ≤ 8 words
- possible_side_effects: max 4 items, each ≤ 6 words (e.g. "Nausea", "Dizziness")
- emergency_warnings: max 2 items, only truly urgent/life-threatening
- All bullets: sentence-case, no trailing period

BULLET STYLE — be extremely terse:
BAD:  "Do not take more than 8 tablets in any 24-hour period"
GOOD: "Max 8 tablets per 24 hours"

BAD:  "Relief of minor aches and pains such as headache, toothache, and muscle pain"
GOOD: "Headache", "Toothache", "Muscle pain"
"""


def build_medicine_insights_prompt(medicine: Medicine) -> str:
    medicine_data = _collect_medicine_data(medicine)
    medicine_json = json.dumps(medicine_data, indent=2, default=str)

    return (
        "Convert this medicine label data into structured insights.\n"
        "Be extremely concise — short phrases, not sentences.\n\n"
        f"{medicine_json}\n\n"
        "Return JSON only."
    )

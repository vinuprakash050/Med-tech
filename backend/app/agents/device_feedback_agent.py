from __future__ import annotations

"""
DeviceFeedbackAgent
===================
Receives raw user survey feedback for a medical device model and uses the
existing LLM provider abstraction to generate a structured pros/cons analysis
for the vendor dashboard.

Falls back to a heuristic keyword-based analyser when:
- The provider is in mock mode (is_mock = True)
- The LLM call fails or returns unparseable JSON
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.dto.device import (
    DeviceFeedbackAnalysis,
    FeedbackEntry,
    FeedbackNegative,
    FeedbackPositive,
)
from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

FEEDBACK_SYSTEM_PROMPT = """\
You are a medical device product analyst. You will receive a batch of real user \
survey reviews for a specific device model and must return a structured JSON \
analysis for the vendor.

OUTPUT: JSON only — no markdown, no explanation, no code fences.
SCHEMA:
{
  "positives": [
    {"point": "<concise positive theme>", "frequency": <int: approx users mentioning this>},
    ...
  ],
  "negatives": [
    {"point": "<concise negative theme>", "frequency": <int: approx users mentioning this>},
    ...
  ],
  "overall_sentiment": "<Highly Positive | Positive | Mixed | Negative | Highly Negative>",
  "summary": "<2-3 sentence executive summary of the overall feedback>",
  "top_improvement_area": "<single most actionable improvement the vendor should address>"
}

RULES:
- Extract 4-7 distinct positive themes and 3-6 distinct negative themes.
- frequency should reflect how many reviews touched on each theme — estimate carefully.
- Be specific and actionable, not generic (avoid "good product" as a positive point).
- Use medical and product domain language appropriate for a vendor analyst.
- Base everything strictly on the review text provided. Do not invent issues or praise.
"""


# ── Heuristic fallback ────────────────────────────────────────────────────────

_POSITIVE_KEYWORDS = [
    ("sound quality", "High-quality audio reproduction"),
    ("comfortable", "Comfortable for extended wear"),
    ("battery", "Strong battery life"),
    ("bluetooth", "Reliable Bluetooth / wireless connectivity"),
    ("waterproof", "Durable waterproof build"),
    ("invisible", "Discreet invisible form factor"),
    ("mri", "MRI-conditional safety clearance"),
    ("remote monitoring", "Remote monitoring capability"),
    ("easy", "Easy to use and fit"),
    ("reliable", "Consistent long-term reliability"),
    ("noise", "Effective noise suppression"),
    ("excellent", "Excellent overall performance"),
]

_NEGATIVE_KEYWORDS = [
    ("app", "Companion app issues or poor UX"),
    ("support", "Customer support responsiveness"),
    ("expensive", "High price point"),
    ("battery", "Battery or charging concerns"),
    ("small", "Very small size causes handling difficulty"),
    ("bulky", "Bulky form factor"),
    ("false alert", "Occasional false alerts or misdetection"),
    ("complicated", "Complex setup or fitting process"),
    ("no bluetooth", "Lack of Bluetooth/wireless features"),
]


def _heuristic_analysis(
    model_name: str,
    brand: str,
    entries: list[FeedbackEntry],
) -> DeviceFeedbackAnalysis:
    """Keyword-scan fallback when LLM is unavailable."""
    pos_counts: dict[str, int] = {}
    neg_counts: dict[str, int] = {}

    for entry in entries:
        text = entry.comment.lower()
        if entry.rating >= 4:
            for kw, label in _POSITIVE_KEYWORDS:
                if kw in text:
                    pos_counts[label] = pos_counts.get(label, 0) + 1
        elif entry.rating <= 2:
            for kw, label in _NEGATIVE_KEYWORDS:
                if kw in text:
                    neg_counts[label] = neg_counts.get(label, 0) + 1

    avg = round(sum(e.rating for e in entries) / len(entries), 1) if entries else 0.0

    positives = sorted(
        [FeedbackPositive(point=k, frequency=v) for k, v in pos_counts.items()],
        key=lambda x: -x.frequency,
    )[:6]

    negatives = sorted(
        [FeedbackNegative(point=k, frequency=v) for k, v in neg_counts.items()],
        key=lambda x: -x.frequency,
    )[:5]

    if not positives:
        positives = [FeedbackPositive(point="General user satisfaction noted", frequency=len([e for e in entries if e.rating >= 4]))]
    if not negatives:
        negatives = [FeedbackNegative(point="Minor usability concerns in low-rated reviews", frequency=len([e for e in entries if e.rating <= 2]))]

    if avg >= 4.5:
        sentiment = "Highly Positive"
    elif avg >= 3.8:
        sentiment = "Positive"
    elif avg >= 3.0:
        sentiment = "Mixed"
    elif avg >= 2.0:
        sentiment = "Negative"
    else:
        sentiment = "Highly Negative"

    top_neg = negatives[0].point if negatives else "No major issues identified"

    return DeviceFeedbackAnalysis(
        model_id="",
        model_name=model_name,
        brand=brand,
        total_reviews=len(entries),
        avg_rating=avg,
        positives=positives,
        negatives=negatives,
        overall_sentiment=sentiment,
        summary=(
            f"{model_name} by {brand} has an average rating of {avg}/5 across "
            f"{len(entries)} user reviews. Sentiment is broadly {sentiment.lower()}. "
            f"Key strengths include {positives[0].point.lower() if positives else 'general performance'}."
        ),
        top_improvement_area=top_neg,
    )


# ── Agent ─────────────────────────────────────────────────────────────────────

class DeviceFeedbackAgent:
    """
    Analyses user survey feedback for a device model using the LLM provider.
    Falls back to heuristic analysis when mock mode or LLM failure occurs.
    """

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm_provider = llm_provider

    def _build_user_prompt(
        self,
        model_name: str,
        brand: str,
        entries: list[FeedbackEntry],
    ) -> str:
        lines = [
            f"Device Model: {model_name}",
            f"Brand: {brand}",
            f"Total Reviews: {len(entries)}",
            f"Average Rating: {round(sum(e.rating for e in entries) / len(entries), 2)}/5",
            "",
            "--- REVIEWS ---",
        ]
        for entry in entries:
            lines.append(
                f"[Rating: {entry.rating}/5 | Date: {entry.date}] {entry.comment}"
            )
        return "\n".join(lines)

    async def analyse(
        self,
        model_id: str,
        model_name: str,
        brand: str,
        entries: list[FeedbackEntry],
    ) -> DeviceFeedbackAnalysis:
        if not entries:
            logger.warning("device_feedback_agent_empty_feedback model_id=%s", model_id)
            return DeviceFeedbackAnalysis(
                model_id=model_id,
                model_name=model_name,
                brand=brand,
                total_reviews=0,
                avg_rating=0.0,
                positives=[],
                negatives=[],
                overall_sentiment="No Data",
                summary="No feedback available for this model.",
                top_improvement_area="Collect more user reviews to generate insights.",
            )

        # Use heuristic for mock provider
        if getattr(self.llm_provider, "is_mock", False):
            logger.info(
                "device_feedback_agent_using_fallback reason=mock_provider model_id=%s",
                model_id,
            )
            result = _heuristic_analysis(model_name, brand, entries)
            result = result.model_copy(update={"model_id": model_id})
            return result

        user_prompt = self._build_user_prompt(model_name, brand, entries)
        llm_logger = logging.getLogger("app.llm")
        llm_logger.info(
            "DeviceFeedbackAgent LLM call start model_id=%s provider=%s",
            model_id,
            type(self.llm_provider).__name__,
        )

        try:
            raw = await self.llm_provider.generate_response_with_system(
                system_prompt=FEEDBACK_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            llm_logger.info(
                "DeviceFeedbackAgent LLM call completed model_id=%s", model_id
            )
        except Exception as exc:
            llm_logger.warning(
                "DeviceFeedbackAgent LLM call failed model_id=%s error=%s — using heuristic fallback",
                model_id,
                exc,
            )
            result = _heuristic_analysis(model_name, brand, entries)
            return result.model_copy(update={"model_id": model_id})

        return self._parse_response(raw, model_id, model_name, brand, entries)

    def _parse_response(
        self,
        raw: str,
        model_id: str,
        model_name: str,
        brand: str,
        entries: list[FeedbackEntry],
    ) -> DeviceFeedbackAnalysis:
        # Strip potential markdown fences
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "device_feedback_agent_json_parse_failed model_id=%s error=%s — using fallback",
                model_id,
                exc,
            )
            result = _heuristic_analysis(model_name, brand, entries)
            return result.model_copy(update={"model_id": model_id})

        avg = round(sum(e.rating for e in entries) / len(entries), 1)

        positives = [
            FeedbackPositive(
                point=str(p.get("point", "")),
                frequency=int(p.get("frequency", 1)),
            )
            for p in data.get("positives", [])
        ]
        negatives = [
            FeedbackNegative(
                point=str(n.get("point", "")),
                frequency=int(n.get("frequency", 1)),
            )
            for n in data.get("negatives", [])
        ]

        return DeviceFeedbackAnalysis(
            model_id=model_id,
            model_name=model_name,
            brand=brand,
            total_reviews=len(entries),
            avg_rating=avg,
            positives=positives,
            negatives=negatives,
            overall_sentiment=str(data.get("overall_sentiment", "Mixed")),
            summary=str(data.get("summary", "")),
            top_improvement_area=str(data.get("top_improvement_area", "")),
        )


# ── Data loader ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DeviceModelMeta:
    model_id: str
    model_name: str
    brand: str


@lru_cache(maxsize=1)
def load_device_data() -> dict:
    """Load full device_data.json once and cache it."""
    data_path = Path(__file__).with_name("device_data.json")
    return json.loads(data_path.read_text(encoding="utf-8"))


def get_feedback_for_model(model_id: str) -> tuple[DeviceModelMeta | None, list[FeedbackEntry]]:
    """
    Look up the model metadata and its feedback entries by model_id.
    Returns (None, []) if the model_id is not found.
    """
    data = load_device_data()

    # Find the model name and brand from devices list
    meta: DeviceModelMeta | None = None
    for device in data.get("devices", []):
        for model in device.get("models", []):
            if model["model_id"] == model_id:
                meta = DeviceModelMeta(
                    model_id=model_id,
                    model_name=model["model_name"],
                    brand=model["brand"],
                )
                break
        if meta:
            break

    if meta is None:
        return None, []

    raw_feedback = data.get("feedback", {}).get(model_id, [])
    entries = [FeedbackEntry(**f) for f in raw_feedback]
    return meta, entries

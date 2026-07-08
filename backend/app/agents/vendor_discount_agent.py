from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from app.prompts.vendor import build_vendor_discount_prompt
from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VendorMedicine:
    id: int
    name: str
    brand: str
    category: str
    expiry_date: str
    stock: int
    previous_sales_7_days: int
    previous_sales_30_days: int
    margin_percent: int


@dataclass(frozen=True)
class VendorRecommendation:
    days_left: int
    urgency_score: int
    discount_percent: int
    action: str
    confidence: str
    reason: str
    prompt: str


@dataclass(frozen=True)
class VendorMedicineCard:
    id: int
    name: str
    brand: str
    category: str
    expiry_date: str
    stock: int
    previous_sales_7_days: int
    previous_sales_30_days: int
    margin_percent: int
    urgency_label: str
    recommendation: VendorRecommendation


@dataclass(frozen=True)
class VendorDashboardSummary:
    medicines_tracked: int
    expiring_within_30_days: int
    clearance_candidates: int
    avg_suggested_discount: int
    total_stock: int


@dataclass(frozen=True)
class VendorDashboardResponse:
    summary: VendorDashboardSummary
    medicines: list[VendorMedicineCard]


class VendorDiscountAgent:
    def __init__(self, llm_provider: BaseLLMProvider | None = None) -> None:
        self.llm_provider = llm_provider

    def _days_until_expiry(self, expiry_date: str) -> int:
        from datetime import datetime

        target = datetime.strptime(expiry_date, "%Y-%m-%d")
        now = datetime.now()
        return (target.date() - now.date()).days

    def _score(self, days_left: int, sales7d: int, stock: int) -> int:
        urgency = max(0, 120 - days_left)
        slow_movement = max(0, 25 - sales7d * 2)
        overstock = max(0, stock - sales7d * 3)
        return min(100, round(urgency * 0.55 + slow_movement * 0.25 + overstock * 0.15))

    def recommend(self, item: VendorMedicine) -> VendorRecommendation:
        days_left = self._days_until_expiry(item.expiry_date)
        urgency_score = self._score(days_left, item.previous_sales_7_days, item.stock)

        weighted = (
            28 if days_left <= 7 else
            22 if days_left <= 14 else
            15 if days_left <= 30 else
            10 if days_left <= 60 else
            5
        )
        sales_boost = 6 if item.previous_sales_7_days < 10 else 3 if item.previous_sales_7_days < 18 else 0
        discount_percent = min(35, max(0, weighted + sales_boost + urgency_score // 25))

        reason = (
            "Expiry is very close, so clearance should be aggressive."
            if days_left <= 7
            else "The batch is approaching expiry and needs a stronger push."
            if days_left <= 30
            else "Sales are slow, so a small incentive can improve movement."
            if item.previous_sales_7_days < 12
            else "Healthy sales pace; keep the discount light."
        )

        action = (
            "Clear fast" if discount_percent >= 25 else
            "Promote now" if discount_percent >= 15 else
            "Test discount" if discount_percent >= 8 else
            "Hold price"
        )
        confidence = "High" if urgency_score >= 75 else "Medium" if urgency_score >= 45 else "Low"
        prompt = build_vendor_discount_prompt(
            item,
            {
                "discount_percent": discount_percent,
                "action": action,
                "confidence": confidence,
            },
        )
        return VendorRecommendation(
            days_left=days_left,
            urgency_score=urgency_score,
            discount_percent=discount_percent,
            action=action,
            confidence=confidence,
            reason=reason,
            prompt=prompt,
        )

    async def _apply_llm(self, recommendation: VendorRecommendation) -> VendorRecommendation:
        if self.llm_provider is None:
            return recommendation

        raw = await self.llm_provider.generate_response(recommendation.prompt)
        data = json.loads(raw)
        return VendorRecommendation(
            days_left=recommendation.days_left,
            urgency_score=recommendation.urgency_score,
            discount_percent=int(data.get("discount_percent", recommendation.discount_percent)),
            action=str(data.get("action", recommendation.action)),
            confidence=str(data.get("confidence", recommendation.confidence)),
            reason=str(data.get("reason", recommendation.reason)),
            prompt=recommendation.prompt,
        )

    async def build_dashboard(self, items: list[VendorMedicine]) -> VendorDashboardResponse:
        async def build_card(item: VendorMedicine) -> VendorMedicineCard:
            baseline = self.recommend(item)
            recommendation = await self._apply_llm(baseline)
            return VendorMedicineCard(
                **asdict(item),
                urgency_label=(
                    "Urgent" if recommendation.days_left <= 7 else
                    "Watch" if recommendation.days_left <= 30 else
                    "Healthy"
                ),
                recommendation=recommendation,
            )

        cards = await asyncio.gather(*(build_card(item) for item in items))
        cards = sorted(cards, key=lambda card: card.recommendation.days_left)

        summary = VendorDashboardSummary(
            medicines_tracked=len(cards),
            expiring_within_30_days=sum(1 for card in cards if card.recommendation.days_left <= 30),
            clearance_candidates=sum(1 for card in cards if card.recommendation.discount_percent >= 15),
            avg_suggested_discount=round(sum(card.recommendation.discount_percent for card in cards) / len(cards)) if cards else 0,
            total_stock=sum(card.stock for card in cards),
        )
        return VendorDashboardResponse(summary=summary, medicines=cards)


@lru_cache(maxsize=1)
def load_vendor_medicines() -> list[VendorMedicine]:
    data_path = Path(__file__).with_name("vendor_data.json")
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    return [VendorMedicine(**item) for item in payload["medicines"]]

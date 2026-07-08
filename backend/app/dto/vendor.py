from pydantic import BaseModel


class VendorMedicineRecommendationResponse(BaseModel):
    days_left: int
    urgency_score: int
    discount_percent: int
    action: str
    confidence: str
    reason: str


class VendorMedicineResponse(BaseModel):
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
    recommendation: VendorMedicineRecommendationResponse


class VendorSummaryResponse(BaseModel):
    medicines_tracked: int
    expiring_within_30_days: int
    clearance_candidates: int
    avg_suggested_discount: int
    total_stock: int


class VendorDashboardResponse(BaseModel):
    summary: VendorSummaryResponse
    medicines: list[VendorMedicineResponse]

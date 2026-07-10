from pydantic import BaseModel, ConfigDict, Field

# Suppress Pydantic protected-namespace warnings for fields starting with "model_"
_ns = ConfigDict(protected_namespaces=())


# ── User-facing DTOs ──────────────────────────────────────────────────────────

class DeviceModelResponse(BaseModel):
    """Single device model card shown to users in search results and detail view."""
    model_config = _ns

    model_id: str
    model_name: str
    brand: str
    price: float
    rating: float
    image_icon: str
    uses: list[str]
    unique_characteristics: list[str]


class DeviceResponse(BaseModel):
    """Top-level device with all its models — returned from list and detail endpoints."""
    id: str
    name: str
    category: str
    search_keywords: list[str]
    models: list[DeviceModelResponse]


class DeviceSearchResultItem(BaseModel):
    """Slim card shown inside main medicine search results."""
    model_config = _ns

    model_id: str
    device_id: str
    device_name: str
    model_name: str
    brand: str
    price: float
    rating: float
    image_icon: str
    uses: list[str]
    unique_characteristics: list[str]
    result_type: str = "device"


class DeviceSearchResponse(BaseModel):
    """Wrapper returned from GET /devices?q=..."""
    query: str
    results: list[DeviceSearchResultItem]


# ── Vendor-facing DTOs ────────────────────────────────────────────────────────

class FeedbackEntry(BaseModel):
    """Single raw survey response."""
    user_id: str
    rating: int = Field(ge=1, le=5)
    comment: str
    date: str


class DeviceFeedbackRequest(BaseModel):
    """Request body for POST /devices/{model_id}/feedback-analysis."""
    model_config = _ns

    model_id: str


class FeedbackPositive(BaseModel):
    point: str
    frequency: int = Field(description="Approximate number of users who mentioned this")


class FeedbackNegative(BaseModel):
    point: str
    frequency: int = Field(description="Approximate number of users who mentioned this")


class DeviceFeedbackAnalysis(BaseModel):
    """AI-generated pros/cons analysis returned to the vendor."""
    model_config = _ns

    model_id: str
    model_name: str
    brand: str
    total_reviews: int
    avg_rating: float
    positives: list[FeedbackPositive]
    negatives: list[FeedbackNegative]
    overall_sentiment: str
    summary: str
    top_improvement_area: str

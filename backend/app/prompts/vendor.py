def _line(item) -> str:
    return (
        f"{item.name} | brand: {item.brand} | category: {item.category} | "
        f"expiry: {item.expiry_date} | stock: {item.stock} | "
        f"sales7d: {item.previous_sales_7_days} | sales30d: {item.previous_sales_30_days} | "
        f"margin: {item.margin_percent}%"
    )


def build_vendor_discount_prompt(item, recommendation: dict[str, object]) -> str:
    return (
        "You are a pharmacy vendor planning assistant.\n"
        "Use only the provided stock, expiry, sales, and margin data.\n"
        "Return valid JSON only. No markdown, no extra text.\n"
        "Use this shape exactly:\n"
        "{"
        "\"discount_percent\": number, "
        "\"action\": string, "
        "\"confidence\": string, "
        "\"reason\": string"
        "}\n\n"
        f"Medicine: {_line(item)}\n"
        f"Baseline recommendation: {recommendation.get('discount_percent')}%\n"
        f"Baseline action: {recommendation.get('action')}\n"
        f"Baseline confidence: {recommendation.get('confidence')}\n"
    )

from app.models.medicine import Medicine


def _fmt(value: str | None, limit: int = 120) -> str:
    """Return a trimmed value or a dash if missing."""
    if not value:
        return "-"
    value = " ".join(value.split())
    return value[:limit] + "…" if len(value) > limit else value


def _medicine_line(medicine: Medicine) -> str:
    """One compact line per medicine — only the fields that matter for comparison."""
    generic_flag = "generic" if medicine.is_generic else "brand"
    return (
        f"{medicine.name} | {medicine.salt_composition} | "
        f"{_fmt(medicine.dosage)} | {_fmt(medicine.dosage_form)} | "
        f"₹{medicine.price} | {generic_flag} | "
        f"purpose: {_fmt(medicine.purpose, 80)}"
    )


def build_recommendation_prompt(
    requested_medicine: Medicine,
    alternatives: list[Medicine],
) -> str:
    if not alternatives:
        return (
            "No cheaper alternatives were found for this medicine.\n"
            "Write one sentence explaining that no lower-priced alternative with the same "
            "salt composition is available in the database.\n"
            "Do not diagnose, prescribe, or suggest stopping any medicine.\n"
            "Plain text only, no markdown.\n\n"
            f"Requested: {_medicine_line(requested_medicine)}"
        )

    alts_block = "\n".join(
        f"  {i+1}. {_medicine_line(m)}"
        for i, m in enumerate(alternatives)
    )

    return (
        "You are a clinical pharmacist explaining medicine alternatives to a patient.\n\n"
        "Requested medicine:\n"
        f"  {_medicine_line(requested_medicine)}\n\n"
        "Alternatives:\n"
        f"{alts_block}\n\n"
        "TASK: Write a single plain-text explanation of 2 to 3 sentences maximum.\n\n"
        "In those sentences cover:\n"
        "  - The shared salt composition and dosage that makes all alternatives safe substitutes.\n"
        "  - The overall price range of savings available across the alternatives.\n"
        "  - One specific standout detail (e.g. the cheapest option, the only brand option, or the generic with the best saving).\n\n"
        "RULES:\n"
        "- Maximum 3 sentences total. No more.\n"
        "- Do NOT list or mention each alternative by name individually.\n"
        "- Do NOT use markdown, bullet points, or headers. Plain prose only.\n"
        "- Do NOT mention warnings, side effects, or give medical advice.\n"
        "- Be specific: use actual salt name, dosage, and price figures from the data."
    )

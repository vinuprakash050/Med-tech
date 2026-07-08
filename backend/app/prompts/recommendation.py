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
        "You are explaining why these medicines are suitable alternatives.\n\n"
        "Requested medicine:\n"
        f"  {_medicine_line(requested_medicine)}\n\n"
        "Alternatives:\n"
        f"{alts_block}\n\n"
        "TASK: Write exactly 2-3 sentences explaining why the alternatives are acceptable.\n"
        "FOCUS ON: matching salt composition, same dosage, lower price, generic status.\n"
        "DO NOT: list every medicine individually, repeat the medicine names more than once each, "
        "mention warnings or side effects, diagnose or prescribe.\n"
        "FORMAT: Plain prose, no markdown, no bullet points, no headers.\n"
        "LENGTH: 2-3 sentences maximum. Be direct and concise."
    )

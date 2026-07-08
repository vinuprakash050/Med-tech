from __future__ import annotations

import re


def normalize_fda_search_term(value: str) -> str:
    """Normalize text for FDA API search queries.

    - lowercase
    - remove dosage (e.g. 500, 650)
    - remove mg/ml units
    - remove special chars
    - keep only meaningful generic terms
    """
    normalized = value.strip().lower()
    # Remove dosage numbers with units
    normalized = re.sub(r"\b\d+\s*(mg|ml|g|mcg|iu|tablet|tab|capsule|cap|injection|syrup)\b", "", normalized, flags=re.IGNORECASE)
    # Remove standalone numbers
    normalized = re.sub(r"\b\d+\b", "", normalized)
    # Remove special chars
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_generic_term(query: str) -> str:
    """Extract the most likely generic term from a user query.

    Examples:
        "Dolo 650" -> "dolo"
        "Azithromycin 500" -> "azithromycin"
        "acetominophen" -> "acetominophen"
        "Azee 500" -> "azee"
    """
    normalized = normalize_fda_search_term(query)
    if not normalized:
        return query.strip().lower()

    # Split into tokens and take the first non-empty, meaningful token
    tokens = normalized.split()
    if not tokens:
        return query.strip().lower()

    # First token is usually the generic/brand name
    return tokens[0]


def truncate_field(value: str | None, max_chars: int = 300) -> str | None:
    """Truncate text field to maximum characters."""
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:max_chars]
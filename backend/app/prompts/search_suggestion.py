from __future__ import annotations


def build_search_suggestion_prompt(query: str, candidate_names: list[str]) -> str:
    candidate_block = "\n".join(f"- {candidate}" for candidate in candidate_names)
    return (
        "You are helping resolve a medicine search using only the candidate medicines below.\n"
        "Candidates may include database medicines and FDA-discovered generics.\n"
        "Return only one candidate name from the list.\n"
        "Do not invent or modify medicine names.\n"
        "Use spelling similarity, likely user intent, and generic name matching.\n"
        "User typed:\n"
        f"{query}\n"
        "Candidate medicines:\n"
        f"{candidate_block}\n"
        "Choose the most likely intended medicine from the candidates.\n"
        "Return ONLY one candidate name."
    )


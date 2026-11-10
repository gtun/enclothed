"""How alike two garments look on paper, for shortlisting owned pieces before an LLM call.

Shared by weigh (#2: "do I already own this?") and mimic (#5: "what do I own that's like this piece?").
The scores only rank. The LLM makes the real judgment, with the shortlist as a hint.
"""
from enclothed import config
from enclothed.models import Garment


def similar_score(candidate: Garment, owned: Garment) -> int:
    """How alike two garments are on paper. Only used to rank; the LLM judges actual similarity."""
    score = 3 if owned.subcategory == candidate.subcategory else 0
    if owned.primary_color == candidate.primary_color:
        score += 2
    elif candidate.primary_color in owned.secondary_colors or owned.primary_color in candidate.secondary_colors:
        score += 1
    if candidate.formality and owned.formality and abs(candidate.formality - owned.formality) <= 1:
        score += 1
    for field in ("fabric_type", "pattern", "fit"):
        value = getattr(candidate, field)
        if value and value == getattr(owned, field):
            score += 1
    return score


def similar_garments(candidate: Garment, owned: dict[int, Garment], limit: int = config.WEIGH_SIMILAR_LIMIT) -> list[int]:
    """IDs of the owned garments in the candidate's category, most alike first (ties: lower ID first)."""
    same_category = [g for g in owned.values() if g.category == candidate.category]
    ranked = sorted(same_category, key=lambda g: (-similar_score(candidate, g), g.id))
    return [g.id for g in ranked[:limit]]

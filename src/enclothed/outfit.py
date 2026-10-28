from anthropic import Anthropic
from enclothed.models import Garment, TokenUsage, Outfit, OutfitResult, Category
from enclothed.llm import recommend_outfits
from enclothed import config
from enclothed.db import insert_outfits
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import get_args

logger = logging.getLogger(__name__)

OUTFIT_INCLUDE_FIELDS = {
    "category","subcategory",
    "primary_color","secondary_colors","accent_colors",
    "materials","warmth","pattern",
    "brand",
    "style_tags",
    "styling_notes",
    "fit","sheen","formality",
}

TEST_OUTFITS = OutfitResult.model_validate({
    "outfits": [
        {
            "aesthetic": "Workwear Americana",
            "garments": [
                {"garment_id": 1, "styling_advice": "nonnative x Undercover black corduroy blouson, worn as the focal piece"},
                {"garment_id": 7, "styling_advice": "cream and navy micro-print heavy cotton shirt, worn buttoned as the mid layer"},
                {"garment_id": 18, "styling_advice": "charcoal twill five-pocket pants with the small purple butterfly"},
                {"garment_id": 22, "styling_advice": "Red Wing cap-toe boots in scuffed amber leather"},
            ],
            "explanation": (
                "Black, cream and charcoal make a neutral base, and the brown boots add warmth. "
                "The cropped jacket sits above the shirt hem, and the straight-leg pants stack cleanly over the boots. "
                "Soft corduroy, thick shirting, slick twill and rugged leather give plenty of texture contrast."
            ),
            "missing": "A plain white or grey heavy tee would give a quieter layer under the blouson than the patterned shirt.",
        },
        {
            "aesthetic": "Japanese Minimal",
            "garments": [
                {"garment_id": 1, "styling_advice": "black corduroy blouson"},
                {"garment_id": 11, "styling_advice": "rust linen band-collar shirt, worn untucked"},
                {"garment_id": 17, "styling_advice": "Issey Miyake me heathered gray wide-leg trousers, high-waisted and cropped"},
                {"garment_id": 23, "styling_advice": "Camper black matte derbies"},
            ],
            "explanation": (
                "The cropped, collarless jacket balances the high-waisted wide trousers. "
                "The longer vented linen hem peeks out below it, and the rust shirt is the single colour note against black and grey. "
                "The collarless jacket, band collar and matte derbies keep the look quiet and clean. "
                "The crinkled linen and fine corduroy give contrast without extra pattern."
            ),
        },
        {
            "aesthetic": "Relaxed Earth-Tone Casual",
            "garments": [
                {"garment_id": 1, "styling_advice": "black corduroy blouson"},
                {"garment_id": 9, "styling_advice": "Needles tan jacquard collarless shirt, worn buttoned and loose"},
                {"garment_id": 16, "styling_advice": "quadro indigo cotton-linen easy pants"},
                {"garment_id": 24, "styling_advice": "Pikolinos cognac leather low-top sneakers"},
            ],
            "explanation": (
                "Tan, indigo and cognac are a natural earthy palette, and the black jacket anchors it as the darkest tone. "
                "The jacquard is low-contrast, so it adds richness without competing with the jacket. "
                "The mid-calf pants and low sneakers keep the lower half light against the boxy, drapey shirt."
            ),
        },
    ]
})


def get_outfits(db_path: Path, wardrobe: dict[int, Garment], anchors: list[int] | None, logging_path: Path, client: Anthropic | None, prompt_message: str, is_test: bool, formality: int = 1, warmth: int = 1) -> OutfitResult:
    # TODO: filters (ADR-039 O8)
    prompt_wardrobe = wardrobe_for_prompt(wardrobe)

    logger.debug(json.dumps(prompt_wardrobe, ensure_ascii=False, indent=2))

    anchors_text = ""
    if anchors:
        anchors_text = "\n<anchors>\n"
        anchors_text += "\n".join(f"{i}: {wardrobe[i].name}" for i in anchors)
        anchors_text += "\n</anchors>"
    context = f"""<wardrobe>
{json.dumps(prompt_wardrobe, ensure_ascii=False)}
</wardrobe>{anchors_text}
<request>{prompt_message}</request>
"""

    wrapper, usage = (TEST_OUTFITS, None) if is_test else recommend_outfits(client, context)

    problems, valid_outfits = validate_outfits(wrapper, wardrobe, anchors)
    for problem in problems:
        logger.warning("Validation: %s", problem)

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if not is_test
        insert_outfits(db_path, valid_outfits, anchors, prompt_message, timestamp)

    log_outfit(logging_path, anchors, wrapper, usage, context, problems, timestamp)

    return wrapper

def wardrobe_for_prompt(wardrobe: dict[int, Garment]) -> dict:
    return {key: value.model_dump(mode="json", include=OUTFIT_INCLUDE_FIELDS) for key, value in wardrobe.items()}

def log_outfit(log_path: Path, anchors: list[int] | None, result: OutfitResult, usage: TokenUsage | None, context: str, problems: list[str], timestamp: str) -> None:
    entry = {
        "timestamp": timestamp,
        "anchors": anchors,
        "usage": usage.model_dump() if usage else None,
        "result": result.model_dump(mode="json"),
        "context": context,
        "problems": problems,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def validate_outfits(result: OutfitResult, wardrobe: dict[int, Garment], anchors: list[int] | None) -> tuple[list[str], list[Outfit]]:
    problems: list[str] = []
    valid: list[Outfit] = []

    count = len(result.outfits)
    if not config.MIN_OUTFIT_SUGGESTIONS <= count <= config.MAX_OUTFIT_SUGGESTIONS:
        problems.append(
            f"{count} outfit(s) returned, expected "
            f"{config.MIN_OUTFIT_SUGGESTIONS}-{config.MAX_OUTFIT_SUGGESTIONS}"
        )

    for number, outfit in enumerate(result.outfits, start=1):
        outfit_problems = validate_outfit(outfit, wardrobe, anchors)
        for problem in outfit_problems:
            problems.append(f"Outfit {number}: {problem}")
        if not outfit_problems:
            valid.append(outfit)

    return problems, valid

def validate_outfit(outfit: Outfit, wardrobe: dict[int, Garment], anchors: list[int] | None) -> list[str]:
    problems = []
    outfit_ids = {g.garment_id for g in outfit.garments}
    missing = set(anchors or []) - outfit_ids
    if missing:
        problems.append(f"anchor(s) {sorted(missing)} missing")

    if len(outfit_ids) < len(outfit.garments):
        problems.append("duplicate garments found in outfit")

    unknown = outfit_ids - wardrobe.keys()

    if unknown:
        problems.append(f"unknown garment id(s) {sorted(unknown)}")
    category_counts = count_categories(outfit_ids - unknown, wardrobe)

    if not ((category_counts["top"] and category_counts["bottom"]) or category_counts["one-piece"]):
        problems.append("body is not covered by a top and a bottom or a one-piece")

    if not category_counts["shoes"]:
        problems.append("outfit has no footwear suggestion")

    if category_counts["shoes"] > 1:
        problems.append("outfit suggests multiple shoes")

    return problems

def count_categories(garment_ids: set[int], wardrobe: dict[int, Garment]) -> dict[str, int]:
    counter = dict.fromkeys(get_args(Category), 0)
    for garment_id in garment_ids:
        counter[wardrobe[garment_id].category] += 1
    return counter

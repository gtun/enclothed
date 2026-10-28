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
            "aesthetic": "Japanese resort casual",
            "garments": [
                {"garment_id": 6, "styling_advice": "Button it up and let it hang loose and untucked"},
                {"garment_id": 15, "styling_advice": "Leave the cropped hem bare to show the shoes"},
                {"garment_id": 27, "styling_advice": "Wear with no-show socks to keep it light"},
            ],
            "explanation": (
                "The drapey printed camp shirt is the one focal point, so the rest stays quiet. "
                "Washed indigo pants and slate-blue sneakers pick up the cool tones in the faded charcoal ground. "
                "Everything is breathable and loose, which suits 21°C sun and a relaxed lunch."
            ),
            "missing": None,
        },
        {
            "aesthetic": "Relaxed earth tones",
            "garments": [
                {"garment_id": 10, "styling_advice": "Wear untucked with the sleeves pushed up"},
                {"garment_id": 73, "styling_advice": "Cuff the hem once for a clean ankle line"},
                {"garment_id": 23, "styling_advice": "Keep the laces neat for a polished casual finish"},
            ],
            "explanation": (
                "Rust linen, khaki chinos and camel leather sneakers make a warm, tonal palette. "
                "The slubby linen against the smooth twill adds texture. "
                "The look is easy and casual, with the slightly cropped chino showing off the sneakers."
            ),
            "missing": None,
        },
        {
            "aesthetic": "Dark minimalist",
            "garments": [
                {"garment_id": 52, "styling_advice": "Let the sleeves bunch slightly at the wrists"},
                {"garment_id": 77, "styling_advice": "Cinch the drawstring and keep the fit easy"},
                {"garment_id": 25, "styling_advice": "Go sockless for an effortless summery feel"},
                {"garment_id": 51, "styling_advice": "Wear open so the hem drapes behind you"},
            ],
            "explanation": (
                "A black long-sleeve tee and tapered pinstripe pants keep the lower half slim under the oversized, draped open jacket. "
                "The palette stays monochrome, with texture from the slubby linen and woven leather mules. "
                "The jacket is light enough for 21°C and easy to take off in the sun."
            ),
            "missing": None,
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

    if not is_test:
        if len(valid_outfits) < len(wrapper.outfits):
            logger.warning("Saving %d of %d outfits", len(valid_outfits), len(wrapper.outfits))
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

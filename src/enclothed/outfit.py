from anthropic import Anthropic
from enclothed.models import Garment, TokenUsage, OutfitSuggestion
from enclothed.llm import recommend_outfits
import logging
import json
from datetime import datetime, timezone
from pathlib import Path

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

TEST_OUTFITS = """Outfit 1: Workwear Americana
- 1: nonnative x Undercover black corduroy blouson, worn as the focal piece
- 8: cream and navy micro-print heavy cotton shirt, worn buttoned as the mid layer
- 18: charcoal twill five-pocket pants with the small purple butterfly
- 22: Red Wing cap-toe boots in scuffed amber leather

Why: Black, cream and charcoal make a neutral base, and the brown boots add warmth. The cropped jacket sits above the shirt hem, and the straight-leg pants stack cleanly over the boots. Soft corduroy, thick shirting, slick twill and rugged leather give plenty of texture contrast.
Missing (optional): A plain white or grey heavy tee would give a quieter layer under the blouson than the patterned shirt.

Outfit 2: Japanese Minimal
- 1: black corduroy blouson
- 11: rust linen band-collar shirt, worn untucked
- 17: Issey Miyake me heathered gray wide-leg trousers, high-waisted and cropped
- 23: Camper black matte derbies

Why: The cropped, collarless jacket balances the high-waisted wide trousers. The longer vented linen hem peeks out below it, and the rust shirt is the single colour note against black and grey. The collarless jacket, band collar and matte derbies keep the look quiet and clean. The crinkled linen and fine corduroy give contrast without extra pattern.

Outfit 3: Relaxed Earth-Tone Casual
- 1: black corduroy blouson
- 9: Needles tan jacquard collarless shirt, worn buttoned and loose
- 16: quadro indigo cotton-linen easy pants
- 24: Pikolinos cognac leather low-top sneakers

Why: Tan, indigo and cognac are a natural earthy palette, and the black jacket anchors it as the darkest tone. The jacquard is low-contrast, so it adds richness without competing with the jacket. The mid-calf pants and low sneakers keep the lower half light against the boxy, drapey shirt.
"""


def get_outfits(wardrobe: dict[int, Garment], anchors: list[int] | None, logging_path: Path, client: Anthropic | None, prompt_message: str, is_test: bool, formality: int = 1, warmth: int = 1) -> str:
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
<occasion>{prompt_message}</occasion>
"""

    outfit_suggestions, usage = (TEST_OUTFITS, None) if is_test else recommend_outfits(client, context)
    log_outfit(logging_path, anchors, outfit_suggestions, usage, context)

    return outfit_suggestions

def wardrobe_for_prompt(wardrobe: dict[int, Garment]) -> dict:
    return {key: value.model_dump(mode="json", include=OUTFIT_INCLUDE_FIELDS) for key, value in wardrobe.items()}

def log_outfit(log_path: Path, anchors: list[int] | None, result: str, usage: TokenUsage | None, context: str) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "anchors": anchors,
        "usage": usage.model_dump() if usage else None,
        #"result": result.model_dump(mode="json"),
        "result": result,
        "context": context,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

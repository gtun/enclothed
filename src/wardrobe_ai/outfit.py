from anthropic import Anthropic
from wardrobe_ai.models import Garment
import logging
import json

logger = logging.getLogger(__name__)

OUTFIT_INCLUDE_FIELDS = {
    "category","subcategory",
    "primary_color","secondary_colors","accent_colors",
    "materials","warmth","pattern",
    "style_tags",
    "styling_notes",
    "fit","sheen","formality",
}

def get_outfits(wardrobe: dict[int, Garment], anchors: list[int] | None, client:Anthropic | None, prompt_message: str, is_test: bool, formality: int = 1, warmth: int = 1):
    print(json.dumps(wardrobe_for_prompt(wardrobe), ensure_ascii=False, indent=2))
    
    return f"{'test ' if is_test else ''}build a wardrobe for {prompt_message} around {[wardrobe[i].name for i in anchors] if anchors else 'no pieces in particular'}"

def wardrobe_for_prompt(wardrobe: dict[int, Garment]) -> dict:
    return {key: value.model_dump(mode="json", include=OUTFIT_INCLUDE_FIELDS) for key, value in wardrobe.items()}

from anthropic import Anthropic
from wardrobe_ai.models import Garment
from wardrobe_ai.llm import recommend_outfits
import logging
import json

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

def get_outfits(wardrobe: dict[int, Garment], anchors: list[int] | None, logging_path: Path, client:Anthropic | None, prompt_message: str, is_test: bool, formality: int = 1, warmth: int = 1):
    logger.debug(json.dumps(wardrobe_for_prompt(wardrobe), ensure_ascii=False, indent=2))
    
    context:str = ""
    
    outfit_suggestions, usage = recommend_outfits(client, context)
    
    log_outfit(logging_path, anchors, outfit_suggestions, usage, prompt_message)
    
    return f"{'test ' if is_test else ''}build a wardrobe for {prompt_message} around {[wardrobe[i].name for i in anchors] if anchors else 'no pieces in particular'}"

def wardrobe_for_prompt(wardrobe: dict[int, Garment]) -> dict:
    return {key: value.model_dump(mode="json", include=OUTFIT_INCLUDE_FIELDS) for key, value in wardrobe.items()}

def log_outfit(log_path: Path, anchors: list[int], result: str, usage: TokenUsage | None, prompt_message: str | None) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "anchors": anchors,
        "usage": usage.model_dump() if usage else None,
        "result": result.model_dump(mode="json"),
        "prompt_message": prompt_message,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

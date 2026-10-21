from anthropic import Anthropic
from wardrobe_ai import models

def get_outfits(wardrobe: dict, anchors: list[int] | None, client:Anthropic | None, prompt_message: str):
    print(f"Anchors: {anchors}\n")
    print(f"Prompt message: {prompt_message}\n")
    return f"build a wardrobe for {prompt_message} around {[wardrobe[i].name for i in anchors] if anchors else 'no pieces in particular'}"

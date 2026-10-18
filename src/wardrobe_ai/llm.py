from anthropic import Anthropic
from wardrobe_ai import config
from wardrobe_ai.models import SUBCATEGORIES, TaggingResult, TokenUsage
import base64
import mimetypes
from pathlib import Path

SUBCATEGORY_TEXT = "\n".join(
    f"- {category}: {', '.join(sorted(subs))}" for category, subs in SUBCATEGORIES.items()
)

TAG_SYSTEM_PROMPT = f"""You catalog garments for a personal wardrobe app.
You receive several photos of ONE garment: the garment itself plus, sometimes,
its labels (brand, care, and fabric content, possibly in Japanese or another language).

Rules:
- subcategory describes shape and construction, never fabric. Fabric goes in materials.
- Textures like corduroy, seersucker, or waffle knit go in style_tags, not pattern.
- Read fabric composition, brand, and country of origin from labels when visible.
  Translate them to English. Put the raw label text in label_text.
- If you cannot determine a field, leave it out rather than guessing.
- styling_notes: 3-5 sentences on the piece's character, what styles it bridges,
  how its proportions behave, and what pairs well with it. Be specific, not generic.
- style_tags are lowercase
- Use accent_colors to describe trims, small panels, contrasting stitching, prominent buttons, and other design features, and not labels

Photo roles:
- Images are labeled "Image 0:", "Image 1:", etc. Return exactly one PhotoTag
  per image, using that number as its index. Every image appears once.
- front: a full view of the garment's front.
- back: a full view of the garment's back.
- detail: a close-up of part of the garment (pocket, buttons, fabric texture).
- label: any tag or label (brand, size, care, fabric content).
- other: anything else.

Allowed subcategories by category:
{SUBCATEGORY_TEXT}
"""

def image_block(path: Path) -> dict:
    media_type, _ = mimetypes.guess_type(path)
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data}
    }
    
def tag_garment(client: Anthropic, photo_paths: list[Path]) -> tuple[TaggingResult, TokenUsage]:
    content = []
    for i, p in enumerate(photo_paths):
        content.append({"type": "text", "text": f"Image {i}:"})
        content.append(image_block(p))
    content.append({"type": "text", "text": "Tag this garment and assign a role to each image."})

    response = client.messages.parse(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        system=TAG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        output_format=TaggingResult,
    )
    usage = TokenUsage(
        model=config.CLAUDE_MODEL,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    print(f"tokens: in={usage.input_tokens} out={usage.output_tokens}")

    if response.parsed_output is None:
        raise RuntimeError(f"No garment in response (stop_reason={response.stop_reason})")
    return response.parsed_output, usage
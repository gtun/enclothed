from anthropic import Anthropic
from anthropic.types import Message
from wardrobe_ai import config
from wardrobe_ai.models import Garment, SUBCATEGORIES
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

Allowed subcategories by category:
{SUBCATEGORY_TEXT}
"""

def call_llm(client:Anthropic) -> Message:
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        
        messages=[
            {
                "role": "user",
                "content": "Hello, Claude",
            }
        ],
    )
    
    return message

def image_block(path: Path) -> dict:
    media_type, _ = mimetypes.guess_type(path)
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data}
    }
    
def tag_garment(client: Anthropic, photo_paths: list[Path]) -> Garment:
    content = [image_block(p) for p in photo_paths]
    content.append({"type": "text", "text": "Tag this garment."})

    response = client.messages.parse(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        system=TAG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        output_format=Garment,
    )
    print(f"tokens: in={response.usage.input_tokens} out={response.usage.output_tokens}")

    if response.parsed_output is None:
        raise RuntimeError(f"No garment in response (stop_reason={response.stop_reason})")
    return response.parsed_output
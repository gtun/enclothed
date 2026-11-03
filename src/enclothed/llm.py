from anthropic import Anthropic
from enclothed import config
from enclothed.models import SUBCATEGORIES, TaggingResult, TokenUsage, OutfitResult, ImprovedPreferences
import base64
import mimetypes
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

SUBCATEGORY_TEXT = "\n".join(
    f"- {category}: {', '.join(sorted(subs))}" for category, subs in SUBCATEGORIES.items()
)

TAG_SYSTEM_PROMPT = f"""You catalog garments for a personal wardrobe app.
You receive several photos of ONE garment: the garment itself plus, sometimes,
its labels (brand, care, and fabric content, possibly in Japanese or another language).

Rules:
- subcategory is the closest listed shape and construction. Put distinguishing details (closures like double-breasted, textures like corduroy) in style_tags and fabric in materials. Use "other" only when no listed shape fits.
- Read fabric composition, brand, and country of origin from labels when visible.
  Translate them to English. Put the raw label text in label_text.
- If you cannot determine a field, leave it out rather than guessing.
- styling_notes: 3-5 sentences on the piece's character, what styles it bridges,
  how its proportions behave, and what pairs well with it. Be specific, not generic.
- Read the user prompt, if provided, for additional details about the garment to adjust the styling_notes and style_tags. Any absolute details from the user take precedence over your evaluation; for example, if the message states the garment's primary color is black, accept it.
- style_tags are lowercase
- fit: how the garment is cut, judged from its proportions in the photos: where the
  shoulder seam falls, sleeve and body width against length, leg width through the
  thigh and hem. A hanger or flat lay shows the cut, not how it sits on a person, so
  judge the cut. If the owner's context states the fit, use theirs. Leave fit out for
  shoes and accessories.
  - slim: cut close to the body; narrow sleeves or legs, little extra room.
  - regular: standard room; neither close nor roomy.
  - relaxed: noticeably roomy; a wider body or legs, possibly dropped shoulders.
  - oversized: deliberately large; shoulders dropped well past the shoulder point,
    a very wide body or legs, extra length.
  Volume that is the design (wide trousers, balloon or sarouel pants, hakama) is
  relaxed or oversized, never regular.
- sheen: how much light the surface reflects, judged from highlights in the photos
  and from the materials. Always fill it; for shoes, judge the main upper.
  - matte: no visible reflection. Brushed or napped cotton, fleece, flannel, most
    knits, wool, linen, canvas, suede, nubuck, roughout leather.
  - low: a soft luster with gentle highlights. Sateen and high-density cotton,
    nylon or polyester shells, smooth or polished leather, mercerized cotton, smooth
    fine-gauge knits.
  - high: clearly shiny, with strong highlights. Satin, patent leather, metallic or
    coated finishes, glossy technical nylon.
- Leave secondary_colors empty for solid garments; shading, heathering and fabric texture are not colors.
- Use accent_colors to describe trims, small panels, contrasting stitching, prominent buttons, and other design features. Do not use accent_colors to describe tags or labels
- White garments under warm light are still white; use cream or beige only when clearly tinted.
- Indigo-dyed fabrics (denim, aizome) are indigo, not navy.

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

OUTFIT_SYSTEM_PROMPT = f"""You suggest outfits from a catalog of garments in one person's wardrobe. You never
see the garments, only their text records.

You receive:
- <wardrobe>: every garment the user owns, as JSON keyed by garment ID.
- <anchors> (optional): garments the user wants to build around.
- <preferences> (optional): the owner's standing tastes and needs, in their own words. Follow
  anything stated as a need or rule (always, never, must) in every outfit. Treat the rest as
  defaults that a specific <request> may override.
- <request>: what the user wants: an occasion, a vibe, or any other request, in their own words.

Reading the records:
- styling_notes describe each piece's visual character and proportions. Rely on them
  for silhouette, since you can't see the photos.
- formality is a cap: the most formal occasion a piece can serve (1 casual, 2 smart
  casual, 3 business, 4 formalwear). A piece can be dressed down, never up.
- warmth (1-5) adds up across layers. Judge the whole outfit against any weather mentioned.
- Treat brand as a signal of each piece's design language, not a reason to group
  pieces by label.

Rules:
- Suggest between {config.MIN_OUTFIT_SUGGESTIONS} and {config.MAX_OUTFIT_SUGGESTIONS} outfits, each in a clearly different aesthetic.
- Every outfit must include every garment listed in <anchors>, if any.
- Choose every other piece from <wardrobe>, using only the IDs shown there. Use each
  garment at most once per outfit.
- An outfit must be complete enough to wear in public: (a top and a bottom) or a
  one-piece, plus shoes. Outerwear and accessories are optional. Layering is allowed.
- Garments sharing a set_id were made to be worn together, but can also be worn separately.

Coordinate each outfit:
- Color: harmonious palette (tonal, neutrals with one accent, or deliberate contrast).
- Silhouette: balanced proportions and volumes, judged from styling_notes.
- Refinement: pieces at a similar level of polish, unless mixing is the point.
- Texture: contrast fabric textures and weights so the outfit isn't flat.
- Focus: at most one focal point; with anchors, usually the anchor.

If the wardrobe can't fully meet the request, build the best outfit you can from it,
then name any missing garments as possible purchases. Never put a garment that isn't
in <wardrobe> inside an outfit.
"""

def image_block(path: Path) -> dict:
    media_type, _ = mimetypes.guess_type(path)
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data}
    }

def tag_garment(client: Anthropic, photo_paths: list[Path], prompt_message: str | None = None) -> tuple[TaggingResult, TokenUsage]:
    content = []
    for i, p in enumerate(photo_paths):
        content.append({"type": "text", "text": f"Image {i}:"})
        content.append(image_block(p))
    content.append({"type": "text", "text": "Tag this garment and assign a role to each image."})
    if prompt_message:
        content.append({"type": "text", "text": f"Additional context from the owner: {prompt_message}"})

    response = client.messages.parse(
        model=config.CLAUDE_MODEL,
        max_tokens=config.TAG_TOKEN_CAP,
        system=TAG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        output_format=TaggingResult,
    )
    usage = TokenUsage(
        model=config.CLAUDE_MODEL,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    logger.debug("tokens: in=%s out=%s", usage.input_tokens, usage.output_tokens)

    if response.parsed_output is None:
        raise RuntimeError(f"No garment in response (stop_reason={response.stop_reason})")
    return response.parsed_output, usage

PREFERENCES_SYSTEM_PROMPT = """You turn a person's description of their clothing tastes and needs into a short,
clear brief for an AI stylist. The stylist reads it before every outfit request, alongside the
person's wardrobe and that day's request.

Rules:
- Keep every fact and wish the person stated. Never add new ones, guess, or generalize.
- Split it into two short bulleted sections, "Needs" (requirements: always, never, must, anything
  about health, accessibility, or comfort) and "Preferences" (tastes and defaults). Leave out an
  empty section.
- Be specific and literal: "loose or relaxed fits; avoid slim fits", not "likes comfort".
- No flattery, no commentary, nothing addressed to the person.
- Under 150 words.
- Write in the language the person used.
- If the text isn't about clothing at all, return it unchanged."""

def improve_preferences(client: Anthropic, text: str) -> tuple[str, TokenUsage]:
    """Rewrite the user's preferences so the outfit LLM can follow them reliably. Saves nothing."""
    response = client.messages.parse(
        model=config.CLAUDE_MODEL,
        max_tokens=config.PREFERENCES_TOKEN_CAP,
        system=PREFERENCES_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"<description>{text}</description>"}],
        output_format=ImprovedPreferences,
    )
    usage = TokenUsage(
        model=config.CLAUDE_MODEL,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
    if response.parsed_output is None:
        raise RuntimeError(f"No rewrite in response (stop_reason={response.stop_reason})")
    return response.parsed_output.text.strip(), usage

def recommend_outfits(client: Anthropic, context: list[dict]) -> tuple[OutfitResult, TokenUsage]:
    response = client.messages.parse(
        model=config.CLAUDE_MODEL,
        max_tokens=config.OUTFIT_TOKEN_CAP,
        system=OUTFIT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
        output_format=OutfitResult,
    )

    usage = TokenUsage(
        model=config.CLAUDE_MODEL,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        cache_creation_input_tokens=response.usage.cache_creation_input_tokens or 0,
        cache_read_input_tokens=response.usage.cache_read_input_tokens or 0,
    )
    logger.debug("tokens: in=%s out=%s cache_creation=%s cache_read=%s", usage.input_tokens, usage.output_tokens, usage.cache_creation_input_tokens, usage.cache_read_input_tokens)
    logger.debug("blocks: %s", [block.type for block in response.content])

    if response.stop_reason == "max_tokens":
        logger.warning("Outfit response cut off at max_tokens (%s)", config.OUTFIT_TOKEN_CAP)
    if response.parsed_output is None:
        raise RuntimeError(f"No outfits in response (stop_reason={response.stop_reason})")
    return response.parsed_output, usage

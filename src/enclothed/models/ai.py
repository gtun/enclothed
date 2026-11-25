"""What the AI calls are asked for and send back. Claude's side of each contract has no optional fields (see the
note above UNKNOWN); some replies, like LookTags and WeighVerdict, are also stored as they are."""
from typing import Any, Literal, get_args
from pydantic import BaseModel, Field, model_validator
from enclothed.fabrics import FABRIC_TYPES
from enclothed.models.terms import Category, Closeness, Color, FabricWeight, Fit, Hem, Recommendation, RiskTier, SUBCATEGORIES, Shape, Sheen, Silhouette, Sleeve, Statement
from enclothed.models.garment import Fiber, Garment, PhotoTag, TaggingResult

# Structured outputs compile the schema into a grammar, and "value or nothing" fields (anyOf with
# null) make that grammar grow fast: past ~15 of them the API answers "Schema is too complex"
# (seen 2026-11-08, after the six attribute fields). So Claude's side of the contract has no
# optional fields at all. Every field is required, and "don't know" is a value: "unknown" for
# fixed lists, 0 for the scales, "" for text. blank_unknowns() turns those back into None, and the
# rest of the app only ever sees Garment. TaggedGarment must list exactly the fields of Garment
# that Claude sees; tests/test_models.py checks that.
UNKNOWN = "unknown"

def _or_unknown(choices: Any) -> Any:
    return Literal[get_args(choices) + (UNKNOWN,)]

class TaggedMaterialPart(BaseModel):
    part: str = Field(description='"shell", "lining", "fill"... Empty for a single-fabric garment.')
    fibers: list[Fiber]

class TaggedGarment(BaseModel):
    category: Category
    subcategory: str
    primary_color: Color
    secondary_colors: list[Color]
    accent_colors: list[Color]
    formality: int = Field(ge=0, le=4,
        description="The most formal occasion it can serve. 1 = casual, 2 = smart casual, 3 = appropriate for business, 4 = formalwear, 0 = can't tell")
    materials: list[TaggedMaterialPart]
    warmth: int = Field(ge=0, le=5,
        description="1 = summer-weight, 25°C+, 2 = light, 18-25°C, 3 = mid-layer, 10-18°C, 4 = warm, 0-10°C, 5 = heavy winter, below 0°C, 0 = can't tell")
    pattern: str
    country_of_origin: str
    style_tags: list[str]
    styling_notes: str
    label_text: str
    fit: _or_unknown(Fit)
    sheen: _or_unknown(Sheen)
    fabric_type: str = Field(description='The main body fabric, from the allowed list, or "unknown"')
    shape: _or_unknown(Shape)
    hem: _or_unknown(Hem)
    fabric_weight: _or_unknown(FabricWeight)
    sleeve: _or_unknown(Sleeve)
    statement: _or_unknown(Statement)
    brand: str

class TaggingReply(BaseModel):
    garment: TaggedGarment
    photos: list[PhotoTag]

def blank_unknowns(fields: dict[str, Any]) -> dict[str, Any]:
    """Claude's "don't know" values ("unknown", 0, "") become None, for fields where Garment allows None."""
    cleaned = {}
    for name, value in fields.items():
        if name == "materials":
            value = [{**part, "part": part.get("part") or None} for part in value]
        elif Garment.model_fields[name].default is None and value in (UNKNOWN, "", 0):
            value = None
        cleaned[name] = value
    return cleaned

def to_tagging_result(reply: TaggingReply) -> TaggingResult:
    """Raises ValidationError when the reply breaks a Garment rule, such as a subcategory off the list."""
    return TaggingResult(garment=Garment(**blank_unknowns(reply.garment.model_dump())), photos=reply.photos)

class TokenUsage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

class ImageUsage(BaseModel):
    """One image-model call's tokens. Text and image input are priced apart, unlike TokenUsage's."""
    model: str
    text_input_tokens: int
    image_input_tokens: int
    output_tokens: int

class OutfitGarment(BaseModel):
    garment_id: int = Field(description="The ID of the suggested garment.")
    styling_advice: str | None = Field(description="One short phrase advising how to wear the garment. Do not refer to the garment by name or description.", default=None)

class Outfit(BaseModel):
    aesthetic: str = Field(description="A short name describing the outfit's aesthetic, for example, 'Workwear Americana' or 'relaxed earth tones.'")
    garments: list[OutfitGarment]
    explanation: str = Field(description="Your rationale for choosing the garments in this outfit")
    missing: str | None = Field(default=None, description="Garments not in the wardrobe that would complete this outfit, and the role each would fill that nothing in the wardrobe can.")
    risk_tier: RiskTier | None = Field(default=None, description="The tier this outfit was built at, as assigned in <options>. Always fill it in.")

class OutfitResult(BaseModel):
    outfits: list[Outfit]


class WeighCheck(BaseModel):
    answer: bool
    reason: str = Field(description="One or two sentences backing the answer with specific garments or facts from the wardrobe.")

class SimilarMatch(BaseModel):
    garment_id: int = Field(description="An ID from <similar>.")
    similarity: Literal["same", "close", "different"] = Field(description="same: does the same job, no need for both. close: overlaps a lot. different: same category, different role.")
    differences: str = Field(description="What sets the candidate apart from this garment, such as color, fabric, fit or length. Short.")

class WeighVerdict(BaseModel):
    """The verdict as it's stored and shown: everything the weigh call returns except the outfits."""
    already_own: WeighCheck
    similar: list[SimilarMatch]
    makes_outfits: WeighCheck
    fills_gap: WeighCheck
    fits_style: WeighCheck
    recommendation: Recommendation
    summary: str

class WeighResult(BaseModel):
    """What the weigh call returns. The model writes fields in this order, so the order is the
    order it reasons in: duplicates first, then outfits, then the checks the outfits inform,
    and the recommendation last, once everything it rests on has been written."""
    already_own: WeighCheck = Field(description="Does the owner already have this garment, or one close enough that they don't need it?")
    similar: list[SimilarMatch] = Field(description="Every garment in <similar>, most similar first.")
    outfits: list[Outfit]
    makes_outfits: WeighCheck = Field(description="Can it make good outfits with what the owner already has? Judge by the outfits above.")
    fills_gap: WeighCheck = Field(description="Does it fill a gap: a role nothing in the wardrobe covers well?")
    fits_style: WeighCheck = Field(description="Does its style fit the wardrobe's overall design language?")
    recommendation: Recommendation = Field(description="worth_it, maybe or pass. A near-duplicate is usually pass.")
    summary: str = Field(description="Two or three sentences the owner can read in the store: the verdict and the main reason.")

    def verdict(self) -> WeighVerdict:
        return WeighVerdict.model_validate(self.model_dump(exclude={"outfits"}))

# mimic, recreating a photographed look, makes two calls. The first looks at the photos once and tags each piece with
# the same fixed values the wardrobe uses, so the second can compare pieces with garments as text, like for like.
class LookPiece(BaseModel):
    """One garment in a photographed look, as stored. Blank where the photos don't show it."""
    category: Category
    subcategory: str
    primary_color: Color
    secondary_colors: list[Color] = []
    pattern: str | None = None
    formality: int | None = Field(default=None, ge=1, le=4)
    warmth: int | None = Field(default=None, ge=1, le=5)
    fit: Fit | None = None
    sheen: Sheen | None = None
    fabric_type: str | None = None
    shape: Shape | None = None
    hem: Hem | None = None
    fabric_weight: FabricWeight | None = None
    sleeve: Sleeve | None = None
    statement: Statement | None = None
    description: str
    role: str
    essential: bool = True

    @model_validator(mode="after")
    def off_list_becomes_other(self):
        """An odd subcategory or fabric becomes "other", so one word never loses a paid call over several pieces."""
        if self.subcategory not in SUBCATEGORIES[self.category]:
            self.subcategory = "other"
        if self.fabric_type is not None and self.fabric_type not in FABRIC_TYPES:
            self.fabric_type = "other"
        return self

    def as_garment(self) -> Garment:
        """The piece as a garment record, for the shortlist and the prompt's field descriptions."""
        fields = self.model_dump(exclude={"description", "role", "essential"})
        return Garment(**fields, styling_notes=self.description)

class LookTags(BaseModel):
    """What the tagging call saw in the photos, as stored."""
    title: str
    summary: str
    silhouette: Silhouette | None = None
    pieces: list[LookPiece]

# Claude's side of the tagging contract: every field required, "don't know" as a value. See the note above
# TaggedGarment for why (optional fields make the structured-output grammar too complex).
class TaggedLookPiece(BaseModel):
    category: Category
    subcategory: str
    primary_color: Color
    secondary_colors: list[Color]
    pattern: str
    formality: int = Field(ge=0, le=4, description="The most formal occasion it can serve. 1 = casual, 2 = smart casual, 3 = appropriate for business, 4 = formalwear, 0 = can't tell")
    warmth: int = Field(ge=0, le=5, description="1 = summer-weight, 25°C+, 2 = light, 18-25°C, 3 = mid-layer, 10-18°C, 4 = warm, 0-10°C, 5 = heavy winter, below 0°C, 0 = can't tell")
    fit: _or_unknown(Fit)
    sheen: _or_unknown(Sheen)
    fabric_type: str = Field(description='The main body fabric, from the allowed list, or "unknown"')
    shape: _or_unknown(Shape)
    hem: _or_unknown(Hem)
    fabric_weight: _or_unknown(FabricWeight)
    sleeve: _or_unknown(Sleeve)
    statement: _or_unknown(Statement)
    description: str = Field(description="One or two sentences on what the fields can't say: cut, proportions, details, how it's worn.")
    role: str = Field(description="What the piece does for the look, in a short phrase, such as 'the volume on top'.")
    essential: bool = Field(description="False for a piece the look would survive without, such as a bag or a watch.")

class LookReply(BaseModel):
    title: str = Field(description="A short name, two to five words, for the look.")
    summary: str = Field(description="Two or three sentences on what makes the look: its proportions, palette, textures and mood.")
    silhouette: _or_unknown(Silhouette) = Field(description="The letter silhouette the whole look forms, or unknown when it forms none clearly.")
    pieces: list[TaggedLookPiece] = Field(description="Every garment, shoe and accessory you can see, outermost layer first.")

def to_look_tags(reply: LookReply) -> LookTags:
    """Claude's "don't know" values become None. Raises ValidationError when a piece breaks a LookPiece rule."""
    pieces = []
    for tagged in reply.pieces:
        fields = tagged.model_dump()
        for name, value in fields.items():
            if LookPiece.model_fields[name].default is None and value in (UNKNOWN, "", 0):
                fields[name] = None
        pieces.append(LookPiece(**fields))
    silhouette = None if reply.silhouette == UNKNOWN else reply.silhouette
    return LookTags(title=reply.title.strip(), summary=reply.summary.strip(), silhouette=silhouette, pieces=pieces)

class PieceMatch(BaseModel):
    piece: int = Field(description="The piece's number in <look>.")
    garment_id: int = Field(description="The owned garment standing in for the piece, from this outfit's garments, or 0 when nothing owned comes close.")
    closeness: Closeness = Field(description="exact: the same piece for practical purposes. close: same kind and color, small differences. loose: does the piece's job in the look, but clearly different. none: nothing owned does its job (garment_id 0).")
    note: str = Field(description="A short phrase on how the stand-in differs from the piece, or what's missing. Empty for an exact match.")

class MimicOutfit(BaseModel):
    """One recreation. The model writes fields in this order: the stand-in for each piece first, then
    the whole outfit, which may add owned pieces for anything the photos don't show."""
    matches: list[PieceMatch] = Field(description="One entry for every piece in <look>, in order.")
    garments: list[OutfitGarment] = Field(description="Every garment in the outfit: the stand-ins above, plus any owned piece added for a part of the body the photos don't show.")
    aesthetic: str = Field(description="A short name for the recreated outfit.")
    explanation: str = Field(description="Two or three sentences: how this recreates the look and where it falls short.")

class MimicResult(BaseModel):
    outfits: list[MimicOutfit] = Field(description="One or two recreations, closest to the look first.")

class OutfitDescription(BaseModel):
    """A name and explanation for an outfit: what the LLM returns, and what the describe endpoint returns."""
    aesthetic: str = Field(description="A short name, two to five words, for the outfit's look or mood, for example, 'Workwear Americana' or 'relaxed earth tones.'")
    explanation: str = Field(description="Two or three sentences on why these pieces work together. Specific to these pieces, never generic.")

class ImprovedPreferences(BaseModel):
    """What the LLM returns when rewriting the user's preferences."""
    text: str = Field(description="The rewritten preferences, ready to send with outfit requests.")


class QueryResult(BaseModel):
    columns: list[str] = []
    rows: list[tuple] = []
    error: str | None = None


class InsightAnswer(BaseModel):
    answer: str
    queries: list[str] = []
    usage: TokenUsage

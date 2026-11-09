import colorsys
from datetime import date
from typing import Any, Literal, get_args
from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema
from enclothed.fabrics import FABRIC_TYPES

Language = Literal["en-US", "zh-TW", "ja-JP"]
DEFAULT_LANGUAGE: Language = "en-US"
LANGUAGE_NAMES: dict[Language, str] = {"en-US": "English", "zh-TW": "繁體中文", "ja-JP": "日本語"}

Color = Literal[
    # neutrals
    "black", "charcoal", "gray", "light gray", "white", "cream",
    "beige", "khaki", "tan", "camel", "brown", "dark brown", "navy",
    # colors
    "light blue", "slate blue", "blue", "indigo", "teal", "green", "olive",
    "forest green", "burgundy", "red", "pink", "orange", "rust",
    "mustard", "yellow", "purple", "eggplant", "lavender", "cognac",
    # metallics
    "silver", "gold", "brass", "copper", "gunmetal"
]
COLOR_HEX: dict[Color, str] = {
    "black": "#151515", "charcoal": "#3b3d42", "gray": "#8a8c90", "light gray": "#c9cacd",
    "white": "#f7f7f5", "cream": "#efe6cf", "beige": "#d9c8a6", "khaki": "#b9a777",
    "tan": "#c19a6b", "camel": "#b5844f", "brown": "#7a4e2d", "dark brown": "#4a2f1d",
    "navy": "#1f2a4a", "light blue": "#a9c4e4", "slate blue": "#5f7391", "blue": "#2f5fb3",
    "indigo": "#1a159a", "teal": "#1f7a7a", "green": "#3c8a4a", "olive": "#6b6a2f",
    "forest green": "#24452e", "burgundy": "#6b1f2e", "red": "#b8322a", "pink": "#e7a1b4",
    "orange": "#e07a2e", "rust": "#a4482a", "mustard": "#c9a227", "yellow": "#eccb3a",
    "purple": "#5e3b8a", "eggplant": "#4b2c45", "lavender": "#b9a7da", "cognac": "#9a5527",
    "silver": "#c0c3c8", "gold": "#c6a14a", "brass": "#b5933f", "copper": "#b06a3b",
    "gunmetal": "#53565c",
}
FORMALITY_LABELS = {1: "casual", 2: "smart casual", 3: "business", 4: "formalwear"}
WARMTH_LABELS = {
    1: "summer-weight, 25°C+", 2: "light, 18–25°C", 3: "mid-layer, 10–18°C",
    4: "warm, 0–10°C", 5: "heavy winter, below 0°C",
}

Fit = Literal["slim", "regular", "relaxed", "oversized"]
Sheen = Literal["matte", "low", "high"]
FIT_LABELS: dict[Fit, str] = {
    "slim": "slim (close to the body)",
    "regular": "regular (standard cut)",
    "relaxed": "relaxed (roomy)",
    "oversized": "oversized (deliberately large)",
}
SHEEN_LABELS: dict[Sheen, str] = {
    "matte": "matte (no shine)",
    "low": "low (soft luster)",
    "high": "high (shiny, like satin or patent leather)",
}
Shape = Literal["straight", "tapered", "wide", "flared", "boxy", "a-line", "balloon"]
Hem = Literal["waist", "hip", "thigh", "knee", "calf", "ankle", "floor"]
FabricWeight = Literal["light", "mid", "heavy"]
Sleeve = Literal["sleeveless", "short", "three-quarter", "long"]
Statement = Literal["basic", "feature", "statement"]
SHAPE_LABELS: dict[Shape, str] = {
    "straight": "straight",
    "tapered": "tapered (narrows toward the hem)",
    "wide": "wide (full throughout)",
    "flared": "flared (widens toward the hem)",
    "boxy": "boxy (wide and short)",
    "a-line": "A-line (wider at the hem)",
    "balloon": "balloon (full through the middle, gathered at the end)",
}
HEM_LABELS: dict[Hem, str] = {
    "waist": "at the waist",
    "hip": "at the hip",
    "thigh": "mid-thigh",
    "knee": "at the knee",
    "calf": "mid-calf",
    "ankle": "at the ankle",
    "floor": "to the floor",
}
FABRIC_WEIGHT_LABELS: dict[FabricWeight, str] = {
    "light": "light",
    "mid": "mid",
    "heavy": "heavy",
}
SLEEVE_LABELS: dict[Sleeve, str] = {
    "sleeveless": "sleeveless",
    "short": "short",
    "three-quarter": "three-quarter",
    "long": "long",
}
STATEMENT_LABELS: dict[Statement, str] = {
    "basic": "basic (quiet, goes with anything)",
    "feature": "feature (some interest of its own)",
    "statement": "statement (the piece people notice)",
}
RiskTier = Literal["safe", "stretch", "bold"]
RISK_TIER_LABELS: dict[RiskTier, str] = {"safe": "Safe", "stretch": "Stretch", "bold": "Bold"}
# The letter shapes an outfit can be asked to form (llm.SILHOUETTE_SECTION says what each means). None: any shape.
Silhouette = Literal["I", "H", "A", "Y", "O", "X"]
Recommendation = Literal["worth_it", "maybe", "pass"]
RECOMMENDATION_LABELS: dict[Recommendation, str] = {"worth_it": "Worth it", "maybe": "Maybe", "pass": "Pass"}

Category = Literal["top", "bottom", "one-piece", "outerwear", "shoes", "accessory"]
CATEGORY_ORDER = {category: position for position, category in enumerate(get_args(Category))}

SUBCATEGORIES: dict[Category, set[str]] = {
    "top": {
        "t-shirt", "long-sleeve t-shirt", "tank top", "polo", "rugby shirt",
        "henley", "oxford shirt", "dress shirt", "casual shirt",
        "camp-collar shirt", "band-collar shirt", "western shirt",
        "flannel shirt", "blouse", "tunic", "smock", "pullover", "no-collar shirt",
        "sweatshirt", "hoodie", "crewneck sweater", "v-neck sweater", "sweater",
        "turtleneck", "mock neck", "cardigan", "sweater vest", "other",
    },
    "bottom": {
        "jeans", "chinos", "dress trousers", "pleated trousers",
        "wide trousers", "easy pants", "balloon pants", "sarouel pants",
        "hakama pants", "work pants", "painter pants", "fatigue pants",
        "cargo pants", "track pants", "joggers", "sweatpants",
        "culottes", "shorts", "skirt", "leggings", "five-pocket pants", "other",
    },
    "one-piece": {
        "overalls", "jumpsuit", "coveralls", "dress", "other",
    },
    "outerwear": {
        # tailored / coats
        "blazer", "sport coat", "overcoat", "trench coat", "pea coat",
        "duffle coat", "suit jacket",
        # jackets
        "trucker jacket", "shirt jacket", "chore coat", "work jacket",
        "field jacket", "safari jacket", "coach jacket", "harrington jacket",
        "bomber jacket", "varsity jacket", "track jacket", "leather jacket",
        "quilted jacket", "liner jacket", "blouson", "no-collar jacket",
        "baseball jacket",
        # Japanese / wrap
        "noragi", "haori", "kimono jacket",
        # technical / weather
        "parka", "puffer jacket", "anorak", "windbreaker", "shell jacket",
        "rain jacket", "fleece",
        # sleeveless / draped
        "vest", "poncho", "cape", "other",
    },
    "shoes": {
        "low-top sneakers", "high-top sneakers", "running shoes",
        "loafers", "oxfords", "derbies", "monk straps", "boat shoes",
        "moccasins", "chelsea boots", "chukka boots", "desert boots",
        "lace-up boots", "engineer boots", "work boots", "hiking boots",
        "sandals", "slides", "clogs", "mules", "espadrilles",
        "tabi", "geta", "other",
    },
    "accessory": {
        "belt", "suspenders", "cap", "bucket hat", "beanie", "flat cap",
        "fedora", "scarf", "stole", "bandana", "tie", "bow tie",
        "pocket square", "socks", "gloves", "tote bag", "backpack",
        "messenger bag", "crossbody bag", "waist bag", "wallet",
        "watch", "glasses", "sunglasses", "jewelry", "other",
    },
}

ALL_SUBCATEGORIES = set().union(*SUBCATEGORIES.values())
LIST_FILTER_CHOICES = sorted(set(CATEGORY_ORDER) | ALL_SUBCATEGORIES)

# --- Worked out from other fields, so they're never tagged or stored ------------
Layer = Literal["base", "mid", "outer"]
MID_LAYERS = {
    "sweatshirt", "hoodie", "crewneck sweater", "v-neck sweater", "sweater", "cardigan",
    "sweater vest", "pullover", "vest", "fleece", "liner jacket",
}

def layer_for(category: Category, subcategory: str) -> Layer | None:
    """Where a piece sits when worn in layers. None for what isn't worn in layers on the torso."""
    if category not in ("top", "outerwear"):
        return None
    if subcategory in MID_LAYERS:
        return "mid"
    return "base" if category == "top" else "outer"

NEUTRAL_COLORS = {
    "black", "charcoal", "gray", "light gray", "white", "cream",
    "beige", "khaki", "tan", "camel", "brown", "dark brown", "navy",
}
METALLIC_COLORS = {"silver", "gold", "brass", "copper", "gunmetal"}

def color_traits(color: Color) -> dict[str, str]:
    """How a stylist would describe a color, worked out from its hex value."""
    red, green, blue = (int(COLOR_HEX[color][i:i + 2], 16) / 255 for i in (1, 3, 5))
    hue, lightness, _ = colorsys.rgb_to_hls(red, green, blue)
    chroma = max(red, green, blue) - min(red, green, blue)   # how far from gray, even in very dark colors
    degrees = hue * 360

    if chroma < 0.05:
        temperature = "neutral"
    elif degrees < 90 or degrees >= 330:
        temperature = "warm"
    else:
        temperature = "cool"

    return {
        "family": "metallic" if color in METALLIC_COLORS else "neutral" if color in NEUTRAL_COLORS else "color",
        "temperature": temperature,
        "lightness": "dark" if lightness < 0.33 else "light" if lightness > 0.66 else "medium",
        "saturation": "muted" if chroma < 0.2 else "vivid" if chroma > 0.45 else "medium",
    }

class Fiber(BaseModel):
    fiber: str
    percent: int = Field(ge=1, le=100)

class MaterialPart(BaseModel):
    part: str | None = None      # "shell", "lining", "fill"... None for a t-shirt
    fibers: list[Fiber]

class Garment(BaseModel):
    id: SkipJsonSchema[int | None] = None
    category: Category
    subcategory: str
    primary_color: Color
    secondary_colors: list[Color] = []
    accent_colors: list[Color] = []
    formality: int | None = Field(default=None, ge=1, le=4,
        description="The most formal occasion it can serve. 1 = casual, 2 = smart casual, 3 = appropriate for business, 4 = formalwear")
    materials: list[MaterialPart] = []
    warmth: int | None = Field(default=None, ge=1, le = 5,
        description="1 = summer-weight, 25°C+, 2 = light, 18-25°C, 3 = mid-layer, 10-18°C, 4 = warm, 0-10°C, 5 = heavy winter, below 0°C")
    pattern: str | None = None
    country_of_origin: str | None = None
    style_tags: list[str] = []
    notes: SkipJsonSchema[str | None] = None
    styling_notes: str
    label_text: str | None = None
    fit: Fit | None = None
    sheen: Sheen | None = None
    fabric_type: str | None = Field(default=None, description="The main body fabric, from the allowed list")
    shape: Shape | None = None
    hem: Hem | None = None
    fabric_weight: FabricWeight | None = None
    sleeve: Sleeve | None = None
    statement: Statement | None = None
    brand: str | None = None
    date_added: SkipJsonSchema[date | None] = None
    set_id: SkipJsonSchema[int | None] = None
    disowned_on: SkipJsonSchema[date | None] = None
    mended_on: SkipJsonSchema[date | None] = None
    user_id: SkipJsonSchema[int | None] = None
    weighed_on: SkipJsonSchema[date | None] = None    # set while it's a candidate from weigh, not owned

    @property
    def name(self) -> str:
        return " ".join(field for field in [self.brand, self.primary_color, self.subcategory] if field)

    @field_validator("fabric_type")
    @classmethod
    def known_fabric(cls, value: str | None) -> str | None:
        """A fabric off the list becomes "other", so one odd word never loses a paid tagging call."""
        return value if value is None or value in FABRIC_TYPES else "other"

    @model_validator(mode="after")
    def check_subcategory(self):
        if self.subcategory not in SUBCATEGORIES[self.category]:
            raise ValueError(f"{self.subcategory!r} is not a valid {self.category} subcategory")
        return self

# --- Mend: which empty fields the LLM can try to fill ------------------------------
MENDABLE_FIELDS = (
    "brand", "formality", "warmth", "fit", "shape", "hem", "sleeve", "fabric_type", "fabric_weight", "sheen",
    "statement", "pattern", "materials", "country_of_origin", "style_tags", "styling_notes", "label_text",
)
CLOTHING = {"top", "bottom", "one-piece", "outerwear"}
# Fields that only make sense for some categories. The rest apply to everything.
FIELD_CATEGORIES: dict[str, set[str]] = {
    "fit": CLOTHING,
    "shape": CLOTHING,
    "hem": CLOTHING,
    "fabric_weight": CLOTHING,
    "sleeve": {"top", "one-piece", "outerwear"},
}

def blank_fields(garment: Garment) -> list[str]:
    """Empty fields that apply to this garment. Secondary and accent colors aren't here: empty means none."""
    return [
        field for field in MENDABLE_FIELDS
        if not getattr(garment, field) and (field not in FIELD_CATEGORIES or garment.category in FIELD_CATEGORIES[field])
    ]


PhotoRole = Literal["front", "back", "detail", "label", "other"]

class PhotoTag(BaseModel):
    index: int
    role: PhotoRole

class TaggingResult(BaseModel):
    garment: Garment
    photos: list[PhotoTag]


# --- What the tagging and mend calls ask Claude for -------------------------------
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


# --- weigh: should I buy this? (#2) ------------------------------------------------
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


# --- Front-end-only models ------------
class Photo(BaseModel):
    role: PhotoRole
    url: str
    thumb_url: str

class GarmentOut(Garment):
    photos: list[Photo] = []
    blank_fields: list[str] = []

class Draft(BaseModel):
    """A tagged garment waiting for its owner to review it. Nothing is in the wardrobe yet."""
    id: str
    garment: Garment
    photos: list[PhotoTag]

class DraftOut(BaseModel):
    id: str
    garment: Garment

class WeighIn(BaseModel):
    """Weigh a tagged draft: the garment as reviewed, which may differ from what the AI tagged."""
    draft_id: str
    garment: Garment

class WeighOut(BaseModel):
    garment_id: int
    weighed_at: str
    verdict: WeighVerdict

class WeighCreatedOut(BaseModel):
    weigh: WeighOut
    candidate: "GarmentOut"
    outfits: list["OutfitOut"]

class MendOut(BaseModel):
    """What the LLM proposes for a garment's blank fields. Nothing has been saved."""
    filled: dict[str, Any]
    unanswered: list[str]

class OutfitGarmentOut(BaseModel):
    garment: GarmentOut
    styling_advice: str | None = None
    is_anchor: bool = False

OutfitSource = Literal["ai", "own"]   # suggested by the AI (weigh included) or put together by the user

class WearOut(BaseModel):
    id: int
    date: str
    notes: str | None = None

class WearIn(BaseModel):
    worn_on: date | None = None   # the day it was worn; the server's today when left out
    notes: str | None = None

class OutfitOut(BaseModel):
    id: int
    timestamp: str
    prompt_message: str
    aesthetic: str
    explanation: str
    missing: str | None = None
    liked: bool | None = None
    risk_tier: RiskTier | None = None
    source: OutfitSource = "ai"
    wear_count: int = 0
    last_worn: str | None = None
    wears: list[WearOut] = []   # newest first
    garments: list[OutfitGarmentOut]

class SetOut(BaseModel):
    id: int
    name: str | None = None

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class OutfitSuggestIn(BaseModel):
    anchors: list[int] = []
    details: str | None = None
    count: int = Field(default=3, ge=1, le=5)
    riskiness: RiskTier | None = None     # None mixes the tiers
    silhouette: Silhouette | None = None  # None leaves the shape to the LLM

class OutfitGarmentIn(BaseModel):
    garment_id: int
    styling_advice: str | None = None

class OutfitCreateIn(BaseModel):
    """An outfit the user put together, saved without the LLM."""
    aesthetic: NonEmptyText
    explanation: NonEmptyText
    missing: str | None = None
    details: str | None = None
    garments: list[OutfitGarmentIn] = Field(min_length=1)

class OutfitDescribeIn(BaseModel):
    """Pieces of an outfit the user put together, to name and explain. A name or explanation already written is kept."""
    garments: list[int] = Field(min_length=1)
    details: str | None = Field(default=None, max_length=1000)
    aesthetic: str | None = Field(default=None, max_length=200)
    explanation: str | None = Field(default=None, max_length=2000)

class OutfitDescription(BaseModel):
    """A name and explanation for an outfit: what the LLM returns, and what the describe endpoint returns."""
    aesthetic: str = Field(description="A short name, two to five words, for the outfit's look or mood, for example, 'Workwear Americana' or 'relaxed earth tones.'")
    explanation: str = Field(description="Two or three sentences on why these pieces work together. Specific to these pieces, never generic.")

class PreferencesOut(BaseModel):
    text: str | None = None
    updated_at: str | None = None

class PreferencesIn(BaseModel):
    text: str | None = Field(default=None, max_length=4000)

class PreferencesImproveIn(BaseModel):
    text: NonEmptyText = Field(max_length=4000)

class ImprovedPreferences(BaseModel):
    """What the LLM returns when rewriting the user's preferences."""
    text: str = Field(description="The rewritten preferences, ready to send with outfit requests.")

class OutfitLikedIn(BaseModel):
    liked: bool | None

class ColorOption(BaseModel):
    name: Color
    hex: str

class LevelOption(BaseModel):
    value: int
    label: str

class ChoiceOption(BaseModel):
    value: str
    label: str

class ProfileOut(BaseModel):
    name: str
    language: Language = DEFAULT_LANGUAGE
    is_admin: bool = False
    signed_in_as: str | None = None   # your own name, when you're in someone else's wardrobe
    is_demo: bool = False             # this is the shared demo wardrobe
    demo_user_id: int | None = None   # how to switch to it; None until the demo has been built

class LanguageIn(BaseModel):
    language: Language

class UserOut(BaseModel):
    id: int
    username: str

class UsageCall(BaseModel):
    """One LLM call, with no prompts or results: only what's needed to review spending."""
    timestamp: str
    user_id: int
    kind: Literal["tagging", "outfits", "style", "insights", "weigh"]
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float | None = None   # None when the model has no price in config

class UsageAllOut(BaseModel):
    """Everyone's usage, for an admin. users includes people with no calls."""
    users: list[UserOut]
    calls: list[UsageCall]

class ActAsIn(BaseModel):
    user_id: int | None = None

class OptionsOut(BaseModel):
    """The fixed choices for editing a garment, so the front end never keeps its own copy."""
    categories: list[Category]
    subcategories: dict[Category, list[str]]
    colors: list[ColorOption]
    fits: list[ChoiceOption]
    sheens: list[ChoiceOption]
    fabric_types: list[ChoiceOption]
    shapes: list[ChoiceOption]
    hems: list[ChoiceOption]
    fabric_weights: list[ChoiceOption]
    sleeves: list[ChoiceOption]
    statements: list[ChoiceOption]
    formality: list[LevelOption]
    warmth: list[LevelOption]
    risk_tiers: list[ChoiceOption] = []
    recommendations: list[ChoiceOption] = []
    languages: list[ChoiceOption]
    # Display names of the fixed values, in the user's language. Empty for English, where the value is the name.
    category_labels: dict[str, str] = {}
    subcategory_labels: dict[str, str] = {}
    color_labels: dict[str, str] = {}
    # Fields that only make sense for some categories. Anything not listed applies to every category.
    field_categories: dict[str, list[Category]] = {}


class User(BaseModel):
    id: int
    username: str
    email: str | None = None
    is_admin: bool = False
    language: Language = DEFAULT_LANGUAGE
    is_demo: bool = False
    demo_reset_at: str | None = None


class QueryResult(BaseModel):
    columns: list[str] = []
    rows: list[tuple] = []
    error: str | None = None


class InsightAnswer(BaseModel):
    answer: str
    queries: list[str] = []
    usage: TokenUsage


class InsightMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: NonEmptyText = Field(max_length=40_000)


class InsightsIn(BaseModel):
    question: NonEmptyText = Field(max_length=2000)
    history: list[InsightMessage] = Field(default=[], max_length=20)

    @model_validator(mode="after")
    def history_takes_turns(self):
        """The conversation has to alternate, starting with the user and ending with the LLM's answer."""
        roles = [message.role for message in self.history]
        expected = ["user", "assistant"] * (len(roles) // 2)
        if roles != expected:
            raise ValueError("history must alternate user and assistant messages, ending with assistant")
        return self


class InsightsOut(BaseModel):
    answer: str
    queries: list[str] = []


WeighCreatedOut.model_rebuild()   # it names OutfitOut, which is defined after it

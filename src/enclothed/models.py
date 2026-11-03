from datetime import date
from typing import Literal, get_args
from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints, model_validator
from pydantic.json_schema import SkipJsonSchema

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
    brand: str | None = None
    date_added: SkipJsonSchema[date | None] = None
    set_id: SkipJsonSchema[int | None] = None
    disowned_on: SkipJsonSchema[date | None] = None

    @property
    def name(self) -> str:
        return " ".join(field for field in [self.brand, self.primary_color, self.subcategory] if field)

    @model_validator(mode="after")
    def check_subcategory(self):
        if self.subcategory not in SUBCATEGORIES[self.category]:
            raise ValueError(f"{self.subcategory!r} is not a valid {self.category} subcategory")
        return self

PhotoRole = Literal["front", "back", "detail", "label", "other"]

class PhotoTag(BaseModel):
    index: int
    role: PhotoRole

class TaggingResult(BaseModel):
    garment: Garment
    photos: list[PhotoTag]

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

class OutfitResult(BaseModel):
    outfits: list[Outfit]


# --- Front-end-only models ------------
class Photo(BaseModel):
    role: PhotoRole
    url: str
    thumb_url: str

class GarmentOut(Garment):
    photos: list[Photo] = []

class OutfitGarmentOut(BaseModel):
    garment: GarmentOut
    styling_advice: str | None = None
    is_anchor: bool = False

class OutfitOut(BaseModel):
    id: int
    timestamp: str
    prompt_message: str
    aesthetic: str
    explanation: str
    missing: str | None = None
    liked: bool | None = None
    wear_count: int = 0
    garments: list[OutfitGarmentOut]

class SetOut(BaseModel):
    id: int
    name: str | None = None

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class OutfitSuggestIn(BaseModel):
    anchors: list[int] = []
    details: str | None = None

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

class OptionsOut(BaseModel):
    """The fixed choices for editing a garment, so the front end never keeps its own copy."""
    categories: list[Category]
    subcategories: dict[Category, list[str]]
    colors: list[ColorOption]
    fits: list[ChoiceOption]
    sheens: list[ChoiceOption]
    formality: list[LevelOption]
    warmth: list[LevelOption]

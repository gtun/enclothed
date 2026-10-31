from datetime import date
from typing import Literal, get_args
from pydantic import BaseModel, Field, model_validator
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
Fit = Literal["slim", "regular", "relaxed", "oversized"]
Sheen = Literal["matte", "low", "high"]
Category = Literal["top", "bottom", "one-piece", "outerwear", "shoes", "accessory"]
CATEGORY_ORDER = {category: position for position, category in enumerate(get_args(Category))}

SUBCATEGORIES: dict[Category, set[str]] = {
    "top": {
        "t-shirt", "long-sleeve t-shirt", "tank top", "polo", "rugby shirt",
        "henley", "oxford shirt", "dress shirt", "casual shirt",
        "camp-collar shirt", "band-collar shirt", "western shirt",
        "flannel shirt", "blouse", "tunic", "smock",
        "sweatshirt", "hoodie", "crewneck sweater", "v-neck sweater",
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

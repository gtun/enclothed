from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

Color = Literal[
    # neutrals
    "black", "charcoal", "gray", "light gray", "white", "cream",
    "beige", "khaki", "tan", "camel", "brown", "dark brown", "navy",
    # colors
    "light blue", "blue", "indigo", "teal", "green", "olive",
    "forest green", "burgundy", "red", "pink", "orange", "rust",
    "mustard", "yellow", "purple", "lavender",
]

Fit = Literal["slim", "regular", "relaxed", "oversized"]
Sheen = Literal["matte", "low", "high"]
Category = Literal["top", "bottom", "one-piece", "outerwear", "shoes", "accessory"]

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
        "culottes", "shorts", "skirt", "leggings", "other",
    },
    "one-piece": {
        "overalls", "jumpsuit", "coveralls", "dress", "other",
    },
    "outerwear": {
        # tailored / coats
        "blazer", "sport coat", "overcoat", "trench coat", "pea coat",
        "duffle coat",
        # jackets
        "trucker jacket", "shirt jacket", "chore coat", "work jacket",
        "field jacket", "safari jacket", "coach jacket", "harrington jacket",
        "bomber jacket", "varsity jacket", "track jacket", "leather jacket",
        "quilted jacket", "liner jacket",
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
    formality: int | None = Field(default=None, ge=1, le=3,
        description="1 = casual, 2 = smart casual, 3 = appropriate for business")
    materials: list[MaterialPart] = []
    warmth: int | None = Field(default=None, ge=1, le = 5,
        description="1 = summer-weight, 3 = mid-layer for 10-15°C, 5 = heavy winter coat")
    pattern: str | None = None
    country_of_origin: str | None = None
    style_tags: list[str] = []
    notes: SkipJsonSchema[str | None] = None
    styling_notes: str
    label_text: str | None = None
    fit: SkipJsonSchema[Fit | None] = None
    sheen: Sheen | None = None
    brand: str | None = None
    wear_count: SkipJsonSchema[int] = 0
    last_worn: SkipJsonSchema[date | None] = None
    date_added: SkipJsonSchema[date | None] = None
    
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
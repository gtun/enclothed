from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator

Color = Literal[
    # neutrals
    "black", "charcoal", "gray", "light gray", "white", "cream",
    "beige", "khaki", "tan", "camel", "brown", "dark brown", "navy",
    # colors
    "light blue", "blue", "indigo", "teal", "green", "olive",
    "forest green", "burgundy", "red", "pink", "orange", "rust",
    "mustard", "yellow", "purple", "lavender",
]
Category = Literal["top", "bottom", "outerwear", "shoes", "accessory"]
Fit = Literal["slim", "regular", "relaxed", "oversized"]
Sheen = Literal["matte", "low", "high"]

SUBCATEGORIES: dict[Category, set[str]] = {
    "top": {
        "t-shirt", "polo", "henley", "tank top", "oxford shirt",
        "dress shirt", "casual shirt", "flannel shirt",
        "sweatshirt", "hoodie", "sweater", "cardigan", "other",
    },
    "bottom": {
        "jeans", "chinos", "dress trousers", "wide trousers",
        "cargo pants", "sweatpants", "shorts", "skirt", "other",
    },
    "outerwear": {
        "blazer", "overcoat", "trench coat", "parka", "puffer jacket",
        "chore coat", "denim jacket", "bomber jacket", "leather jacket",
        "rain jacket", "fleece", "vest", "other",
    },
    "shoes": {
        "sneakers", "running shoes", "loafers", "oxfords", "derbies",
        "chelsea boots", "work boots", "sandals", "other",
    },
    "accessory": {
        "belt", "hat", "cap", "beanie", "scarf", "tie", "socks",
        "gloves", "bag", "watch", "sunglasses", "other",
    },
}

class Fiber(BaseModel):
    fiber: str
    percent: int = Field(ge=1, le=100)

class MaterialPart(BaseModel):
    part: str | None = None      # "shell", "lining", "fill"... None for a t-shirt
    fibers: list[Fiber]
    
class Garment(BaseModel):
    id: int | None = None
    category: Category
    subcategory: str
    primary_color: Color
    secondary_colors: list[Color] = []
    accent_colors: list[Color] = []
    formality: int | None = Field(default=None, ge=1, le=3)
    materials: list[MaterialPart] = []
    warmth: int | None = Field(default=None, ge=1, le = 5)
    pattern: str | None = None
    country_of_origin: str | None = None
    style_tags: list[str] = []
    notes: str | None = None
    label_text: str | None = None
    fit: Fit | None = None
    sheen: Sheen | None = None
    brand: str | None = None
    wear_count: int = 0
    last_worn: date | None = None

    @model_validator(mode="after")
    def check_subcategory(self):
        if self.subcategory not in SUBCATEGORIES[self.category]:
            raise ValueError(f"{self.subcategory!r} is not a valid {self.category} subcategory")
        return self
    

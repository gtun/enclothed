"""A garment as the wardrobe holds it, the fields mend can fill, and how its photos are tagged."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema
from enclothed.fabrics import FABRIC_TYPES
from enclothed.models.terms import Category, Color, FabricWeight, Fit, Hem, SUBCATEGORIES, Shape, Sheen, Sleeve, Statement

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

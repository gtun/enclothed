"""What the API takes in (*In) and sends back (*Out), and the parts they're built from."""
from datetime import date
from typing import Any, Literal
from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints, model_validator
from enclothed.models.terms import Category, Color, DEFAULT_LANGUAGE, Language, OutfitSource, RiskTier, Silhouette
from enclothed.models.garment import Garment, PhotoRole, blank_fields
from enclothed.models.ai import LookPiece
from enclothed.models.records import LookMatch, Wear, Weigh

class LookMatchOut(LookMatch):
    pass

class LookRecreationOut(BaseModel):
    outfit_id: int
    matches: list[LookMatchOut]

class LookPhoto(BaseModel):
    url: str
    thumb_url: str

class LookOut(BaseModel):
    id: int
    created_at: str
    note: str | None = None
    title: str
    summary: str
    silhouette: Silhouette | None = None
    pieces: list[LookPiece]
    photos: list[LookPhoto] = []
    recreations: list[LookRecreationOut] = []   # closest first; empty when nothing in the wardrobe could make the look


class Photo(BaseModel):
    role: PhotoRole
    url: str
    thumb_url: str

class GarmentOut(Garment):
    photos: list[Photo] = []
    blank_fields: list[str] = []

class DraftOut(BaseModel):
    id: str
    garment: Garment

class WeighIn(BaseModel):
    """Weigh a tagged draft: the garment as reviewed, which may differ from what the AI tagged."""
    draft_id: str
    garment: Garment

class WeighOut(Weigh):
    pass

class WeighCreatedOut(BaseModel):
    weigh: WeighOut
    candidate: "GarmentOut"
    outfits: list["OutfitOut"]

class MimicCreatedOut(BaseModel):
    """A look and the outfits just made to recreate it."""
    look: LookOut
    outfits: list["OutfitOut"]

class MendOut(BaseModel):
    """What the LLM proposes for a garment's blank fields. Nothing has been saved."""
    filled: dict[str, Any]
    unanswered: list[str]

class OutfitGarmentOut(BaseModel):
    garment: GarmentOut
    styling_advice: str | None = None
    is_anchor: bool = False

class WearOut(Wear):
    pass

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

class PreferencesOut(BaseModel):
    text: str | None = None
    updated_at: str | None = None

class PreferencesIn(BaseModel):
    text: str | None = Field(default=None, max_length=4000)

class PreferencesImproveIn(BaseModel):
    text: NonEmptyText = Field(max_length=4000)

class ReworkIn(BaseModel):
    """What to change in a garment's photo, in the person's own words."""
    instruction: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]

class ReworkOut(BaseModel):
    """An edited image of one of a garment's photos. It's a preview, never one of the garment's photos."""
    id: int
    garment_id: int
    instruction: str
    url: str
    created_at: str

class ReworkAllowanceOut(BaseModel):
    """How many reworks are left today: only the demo has a limit, so left is None everywhere else."""
    left: int | None

class ShareIn(BaseModel):
    """Make a share link to one of your garments or outfits."""
    kind: Literal["garment", "outfit"]
    id: int

class ShareCreatedOut(BaseModel):
    path: str          # "/s/<token>": the page joins it to its own address
    expires_at: str

class ShareOut(BaseModel):
    """One of your live share links, as the Shared links page lists it. The page builds the label:
    an outfit's aesthetic, or a garment's brand and (translated) subcategory."""
    token: str
    path: str          # "/s/<token>", like ShareCreatedOut
    kind: Literal["garment", "outfit"]
    created_at: str
    expires_at: str
    aesthetic: str | None = None     # outfits
    brand: str | None = None         # garments
    subcategory: str | None = None   # garments, in English like everywhere else
    max_expires_at: str               # the latest it can expire, however often it's extended

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

class LLMModelOut(BaseModel):
    id: str
    name: str
    features: list[str]   # the config.MODELS_BY_PROVIDER feature keys that use it

class LLMOut(BaseModel):
    """One provider in the admin's LLM picker."""
    provider: str
    name: str
    models: list[LLMModelOut]
    is_default: bool      # what runs when the page picks nothing

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
    kind: Literal["tagging", "outfits", "style", "insights", "weigh", "mimic", "rework"]
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
    closeness: list[ChoiceOption] = []
    languages: list[ChoiceOption]
    # Display names of the fixed values, in the user's language. Empty for English, where the value is the name.
    category_labels: dict[str, str] = {}
    subcategory_labels: dict[str, str] = {}
    color_labels: dict[str, str] = {}
    # Fields that only make sense for some categories. Anything not listed applies to every category.
    field_categories: dict[str, list[Category]] = {}


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
MimicCreatedOut.model_rebuild()

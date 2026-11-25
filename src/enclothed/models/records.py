"""What the database (and the drafts folder) holds, as db.py returns it. responses.py builds the *Out models from
these; an *Out model with the same fields subclasses its record."""
from datetime import date
from typing import Literal
from pydantic import BaseModel
from enclothed.models.terms import Closeness, DEFAULT_LANGUAGE, Language, OutfitSource, RiskTier
from enclothed.models.garment import Garment, PhotoTag
from enclothed.models.ai import LookTags, WeighVerdict

class LookMatch(BaseModel):
    """What stands in for one piece of a look in one recreation, as stored."""
    piece: int
    garment_id: int | None = None   # None: nothing owned stood in for it
    closeness: Closeness
    note: str | None = None

class LookRecreation(BaseModel):
    """One outfit made to recreate a look, with what stands in for each piece."""
    outfit_id: int
    matches: list[LookMatch]

class Look(LookTags):
    """A saved look, as the database holds it: what was tagged, the note, and its recreations, closest first.
    LookOut is what the API sends."""
    id: int
    created_at: str
    note: str | None = None
    recreations: list[LookRecreation] = []

class Draft(BaseModel):
    """A tagged garment waiting for its owner to review it. Nothing is in the wardrobe yet."""
    id: str
    garment: Garment
    photos: list[PhotoTag]

class Weigh(BaseModel):
    """A candidate's verdict, as the database holds it."""
    garment_id: int
    weighed_at: str
    verdict: WeighVerdict

class Wear(BaseModel):
    """One logged wear of an outfit, as stored."""
    id: int
    date: str
    notes: str | None = None

class SavedOutfitGarment(BaseModel):
    """One garment in a saved outfit, by id. OutfitGarmentOut is the same with the whole garment."""
    garment_id: int
    styling_advice: str | None = None
    is_anchor: bool = False

class SavedOutfit(BaseModel):
    """An outfit as the database holds it. Outfit is what the AI suggests, before it's saved; OutfitOut is what
    the API sends, with each garment in full."""
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
    wears: list[Wear] = []   # newest first
    garments: list[SavedOutfitGarment]

class Rework(BaseModel):
    """A saved rework, as the database holds it. ReworkOut is what the API sends: no model or source photo, and a url."""
    id: int
    garment_id: int
    instruction: str
    source_photo: str   # the garment photo it was made from, by file name
    model: str          # the image model that made it
    created_at: str

class Share(BaseModel):
    """A share link as the database holds it, minus who made it. The snapshot stays a dict: it's the frozen copy of
    the page that share.html shows, in the shape shares.py built it."""
    token: str
    kind: Literal["garment", "outfit"]
    created_at: str
    expires_at: str
    snapshot: dict


class User(BaseModel):
    id: int
    username: str
    email: str | None = None
    is_admin: bool = False
    language: Language = DEFAULT_LANGUAGE
    is_demo: bool = False
    demo_reset_at: str | None = None

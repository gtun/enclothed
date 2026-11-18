"""Builds the *Out models the API sends, from database records and photo folders."""
from datetime import datetime, timedelta
from pathlib import Path
from enclothed import db, i18n
from typing import get_args
from enclothed.models import (
    CATEGORY_ORDER, Category, Color, FIELD_CATEGORIES, FabricWeight, Fit, Hem, Shape, Sheen, Sleeve, Statement, RiskTier, Recommendation, Closeness, SUBCATEGORIES, COLOR_HEX, FABRIC_WEIGHT_LABELS,
    FIT_LABELS, HEM_LABELS, SHAPE_LABELS, SHEEN_LABELS, SLEEVE_LABELS, STATEMENT_LABELS, RISK_TIER_LABELS, RECOMMENDATION_LABELS, CLOSENESS_LABELS, FORMALITY_LABELS, WARMTH_LABELS,
    ChoiceOption, ColorOption, DEFAULT_LANGUAGE, Garment, GarmentOut, LANGUAGE_NAMES, Language, LevelOption, LookOut, OptionsOut,
    OutfitGarmentOut, OutfitOut, SetOut, ShareOut, blank_fields,
)
from enclothed.config import SHARE_MAX_LIFETIME_DAYS
from enclothed.fabrics import FABRIC_TYPES
from enclothed.photos import get_garment_photos, get_look_photos

def to_garment_out(garment: Garment) -> GarmentOut:
    return GarmentOut(**garment.model_dump(), photos=get_garment_photos(garment.id), blank_fields=blank_fields(garment))

def get_garment(db_path: Path, user_id: int, garment_id: int) -> GarmentOut | None:
    garment = db.select_garment(db_path, user_id, garment_id)
    return to_garment_out(garment) if garment else None

def list_garments(db_path: Path, user_id: int) -> list[GarmentOut]:
    return [to_garment_out(garment) for garment in db.select_all_garments(db_path, user_id)]

def _wardrobe_by_id(db_path: Path, user_id: int) -> dict[int, GarmentOut]:
    return {garment.id: garment for garment in list_garments(db_path, user_id)}

def _to_outfit_out(outfit: dict, wardrobe: dict[int, GarmentOut]) -> OutfitOut:
    garments = [
        OutfitGarmentOut(
            garment=wardrobe[entry["garment_id"]],
            styling_advice=entry["styling_advice"],
            is_anchor=entry["is_anchor"],
        )
        for entry in outfit["garments"]
    ]
    return OutfitOut(**{**outfit, "garments": garments})

def get_outfit(db_path: Path, user_id: int, outfit_id: int) -> OutfitOut | None:
    outfit = db.select_outfit(db_path, user_id, outfit_id)
    if outfit is None:
        return None
    return _to_outfit_out(outfit, _wardrobe_by_id(db_path, user_id))

def get_outfits(db_path: Path, user_id: int, outfit_ids: list[int]) -> list[OutfitOut]:
    outfits = [db.select_outfit(db_path, user_id, outfit_id) for outfit_id in outfit_ids]
    wardrobe = _wardrobe_by_id(db_path, user_id)
    return [_to_outfit_out(outfit, wardrobe) for outfit in outfits if outfit is not None]

def list_outfits(db_path: Path, user_id: int) -> list[OutfitOut]:
    outfits = db.select_all_outfits(db_path, user_id)
    wardrobe = _wardrobe_by_id(db_path, user_id)
    return [_to_outfit_out(outfit, wardrobe) for outfit in outfits]

def to_look_out(look: dict) -> LookOut:
    return LookOut(**look, photos=get_look_photos(look["id"]))

def get_look(db_path: Path, user_id: int, look_id: int) -> LookOut | None:
    look = db.select_look(db_path, user_id, look_id)
    return to_look_out(look) if look else None

def list_looks(db_path: Path, user_id: int) -> list[LookOut]:
    return [to_look_out(look) for look in db.select_looks(db_path, user_id)]

def list_sets(db_path: Path, user_id: int) -> list[SetOut]:
    return [SetOut(id=set_id, name=name) for set_id, name in db.select_all_sets(db_path, user_id).items()]

def max_share_expiry(created_at: str) -> str:
    """The latest a link made at created_at can expire, however often it's extended. Here rather than in
    shares.py, which imports this module, so the list and extend share one definition."""
    return (datetime.fromisoformat(created_at) + timedelta(days=SHARE_MAX_LIFETIME_DAYS)).isoformat(timespec="seconds")

def _to_share_out(share: dict) -> ShareOut:
    """Only what the list shows from a snapshot: enough for a label."""
    snapshot = share["snapshot"]
    outfit, garment = snapshot.get("outfit") or {}, snapshot.get("garment") or {}
    return ShareOut(token=share["token"], path=f"/s/{share['token']}", kind=share["kind"],
                    created_at=share["created_at"], expires_at=share["expires_at"],
                    max_expires_at=max_share_expiry(share["created_at"]),
                    aesthetic=outfit.get("aesthetic"), brand=garment.get("brand"), subcategory=garment.get("subcategory"))

def list_shares(db_path: Path, user_id: int, now: str) -> list[ShareOut]:
    """This user's live share links, newest first."""
    return [_to_share_out(share) for share in db.select_user_shares(db_path, user_id, now)]

def get_share(db_path: Path, user_id: int, token: str, now: str) -> ShareOut | None:
    share = db.select_user_share(db_path, token, user_id, now)
    return _to_share_out(share) if share else None

def _sorted_other_last(values: set[str]) -> list[str]:
    return sorted(values, key=lambda value: (value == "other", value))

def get_options(language: Language = DEFAULT_LANGUAGE) -> OptionsOut:
    terms = i18n.terms(language)

    def label(group: str, value: str | int, english: str) -> str:
        return terms.get(group, {}).get(str(value), english)

    fabrics = [ChoiceOption(value=fabric, label=label("fabric_types", fabric, fabric)) for fabric in FABRIC_TYPES]
    fabrics.sort(key=lambda option: (option.value == "other", option.label))

    return OptionsOut(
        categories=list(get_args(Category)),
        subcategories={category: _sorted_other_last(SUBCATEGORIES[category]) for category in get_args(Category)},
        colors=[ColorOption(name=color, hex=COLOR_HEX[color]) for color in get_args(Color)],
        fits=[ChoiceOption(value=fit, label=label("fits", fit, FIT_LABELS[fit])) for fit in get_args(Fit)],
        sheens=[ChoiceOption(value=sheen, label=label("sheens", sheen, SHEEN_LABELS[sheen])) for sheen in get_args(Sheen)],
        fabric_types=fabrics,
        shapes=[ChoiceOption(value=shape, label=label("shapes", shape, SHAPE_LABELS[shape])) for shape in get_args(Shape)],
        hems=[ChoiceOption(value=hem, label=label("hems", hem, HEM_LABELS[hem])) for hem in get_args(Hem)],
        fabric_weights=[ChoiceOption(value=weight, label=label("fabric_weights", weight, FABRIC_WEIGHT_LABELS[weight])) for weight in get_args(FabricWeight)],
        sleeves=[ChoiceOption(value=sleeve, label=label("sleeves", sleeve, SLEEVE_LABELS[sleeve])) for sleeve in get_args(Sleeve)],
        statements=[ChoiceOption(value=statement, label=label("statements", statement, STATEMENT_LABELS[statement])) for statement in get_args(Statement)],
        formality=[LevelOption(value=value, label=label("formality", value, text)) for value, text in FORMALITY_LABELS.items()],
        warmth=[LevelOption(value=value, label=label("warmth", value, text)) for value, text in WARMTH_LABELS.items()],
        risk_tiers=[ChoiceOption(value=tier, label=label("risk_tiers", tier, RISK_TIER_LABELS[tier])) for tier in get_args(RiskTier)],
        recommendations=[ChoiceOption(value=r, label=label("recommendations", r, RECOMMENDATION_LABELS[r])) for r in get_args(Recommendation)],
        closeness=[ChoiceOption(value=c, label=label("closeness", c, CLOSENESS_LABELS[c])) for c in get_args(Closeness)],
        languages=[ChoiceOption(value=value, label=name) for value, name in LANGUAGE_NAMES.items()],
        category_labels=terms.get("categories", {}),
        subcategory_labels=terms.get("subcategories", {}),
        color_labels=terms.get("colors", {}),
        field_categories={field: sorted(categories, key=CATEGORY_ORDER.get) for field, categories in FIELD_CATEGORIES.items()},
    )

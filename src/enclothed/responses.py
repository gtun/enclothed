"""Builds the *Out models the API sends, from database records and photo folders."""
from pathlib import Path
from enclothed import db
from typing import get_args
from enclothed.models import (
    Category, Color, Fit, Sheen, SUBCATEGORIES, COLOR_HEX, FIT_LABELS, SHEEN_LABELS, FORMALITY_LABELS, WARMTH_LABELS,
    ChoiceOption, ColorOption, Garment, GarmentOut, LevelOption, OptionsOut, OutfitGarmentOut, OutfitOut, SetOut,
)
from enclothed.photos import get_garment_photos

def to_garment_out(garment: Garment) -> GarmentOut:
    return GarmentOut(**garment.model_dump(), photos=get_garment_photos(garment.id))

def get_garment(db_path: Path, garment_id: int) -> GarmentOut | None:
    garment = db.select_garment(db_path, garment_id)
    return to_garment_out(garment) if garment else None

def list_garments(db_path: Path) -> list[GarmentOut]:
    return [to_garment_out(garment) for garment in db.select_all_garments(db_path)]

def _wardrobe_by_id(db_path: Path) -> dict[int, GarmentOut]:
    return {garment.id: garment for garment in list_garments(db_path)}

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

def get_outfit(db_path: Path, outfit_id: int) -> OutfitOut | None:
    outfit = db.select_outfit(db_path, outfit_id)
    if outfit is None:
        return None
    return _to_outfit_out(outfit, _wardrobe_by_id(db_path))

def get_outfits(db_path: Path, outfit_ids: list[int]) -> list[OutfitOut]:
    outfits = [db.select_outfit(db_path, outfit_id) for outfit_id in outfit_ids]
    wardrobe = _wardrobe_by_id(db_path)
    return [_to_outfit_out(outfit, wardrobe) for outfit in outfits if outfit is not None]

def list_outfits(db_path: Path) -> list[OutfitOut]:
    outfits = db.select_all_outfits(db_path)
    wardrobe = _wardrobe_by_id(db_path)
    return [_to_outfit_out(outfit, wardrobe) for outfit in outfits]

def list_sets(db_path: Path) -> list[SetOut]:
    return [SetOut(id=set_id, name=name) for set_id, name in db.select_all_sets(db_path).items()]

def _sorted_other_last(values: set[str]) -> list[str]:
    return sorted(values, key=lambda value: (value == "other", value))

def get_options() -> OptionsOut:
    return OptionsOut(
        categories=list(get_args(Category)),
        subcategories={category: _sorted_other_last(SUBCATEGORIES[category]) for category in get_args(Category)},
        colors=[ColorOption(name=color, hex=COLOR_HEX[color]) for color in get_args(Color)],
        fits=[ChoiceOption(value=fit, label=FIT_LABELS[fit]) for fit in get_args(Fit)],
        sheens=[ChoiceOption(value=sheen, label=SHEEN_LABELS[sheen]) for sheen in get_args(Sheen)],
        formality=[LevelOption(value=value, label=label) for value, label in FORMALITY_LABELS.items()],
        warmth=[LevelOption(value=value, label=label) for value, label in WARMTH_LABELS.items()],
    )

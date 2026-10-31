"""Builds the *Out models the API sends, from database records and photo folders."""
from pathlib import Path
from enclothed import db
from enclothed.models import Garment, GarmentOut, OutfitGarmentOut, OutfitOut
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

def list_outfits(db_path: Path) -> list[OutfitOut]:
    outfits = db.select_all_outfits(db_path)
    wardrobe = _wardrobe_by_id(db_path)
    return [_to_outfit_out(outfit, wardrobe) for outfit in outfits]

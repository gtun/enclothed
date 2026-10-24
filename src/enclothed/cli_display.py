from enclothed.models import Garment, Outfit, OutfitGarment, OutfitResult, CATEGORY_ORDER
from enum import Enum

class GarmentDisplayFormat(Enum):
    NAME = 1
    ID = 2
    NAME_AND_ID = 3

def format_garment_id_name(garment: Garment) -> str:
    return f"{garment.id:>3}  {garment.name}"

def format_list(wardrobe: list[Garment]) -> str:
    wardrobe = sorted(wardrobe, key=lambda garment: (CATEGORY_ORDER[garment.category], garment.subcategory, garment.id),)

    list_str = ""

    for category in CATEGORY_ORDER:
        list_str += (f"{category.upper()} {'=' * (45 - len(category))}\n")
        for garment in wardrobe:
            if garment.category == category:
                list_str +=f"  {format_garment_id_name(garment)}\n"

    return list_str

def format_new_garment(garment: Garment) -> str:
    return f"new garment added:\n  {format_garment_id_name(garment)}"

def format_outfit():
    pass

def format_outfit_result():
    pass

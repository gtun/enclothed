from enclothed.models import Garment, Outfit, OutfitGarment, OutfitResult, CATEGORY_ORDER
from enum import Enum

def format_garment_id_name(garment: Garment) -> str:
    return f"{garment.id:>3}  {garment.name}"

def format_list(wardrobe: list[Garment]) -> str:
    list_str_array = []
    current_category = ""

    for garment in wardrobe:
        if garment.category != current_category:
            current_category = garment.category
            list_str_array.append((f"\n{garment.category.upper()} {'=' * (45 - len(garment.category))}"))
        list_str_array.append(f"  {format_garment_id_name(garment)}")

    return "\n".join(list_str_array)

def format_new_garment(garment: Garment) -> str:
    return f"\nnew garment added:\n  {format_garment_id_name(garment)}"

def format_outfit():
    pass

def format_outfit_result():
    pass

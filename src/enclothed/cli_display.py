from enclothed.models import Garment, Outfit, OutfitGarment, OutfitResult, CATEGORY_ORDER

def format_garment_id_name(garment: Garment) -> str:
    return f"{garment.id:>3}  {garment.name}"

def format_list(wardrobe: list[Garment]) -> str | None:
    lines = []
    current_category = ""

    wardrobe = sorted(wardrobe, key=lambda garment: (CATEGORY_ORDER[garment.category], garment.name.casefold(), garment.id),)

    for garment in wardrobe:
        if garment.category != current_category:
            if current_category != "":
                lines.append("")
            current_category = garment.category
            lines.append(f"{garment.category.upper()} {'=' * (45 - len(garment.category))}")
        lines.append(f"  {format_garment_id_name(garment)}")

    return "\n".join(lines) if lines else None

def format_new_garment(garment: Garment) -> str:
    return f"new garment added:\n  {format_garment_id_name(garment)}"

def format_outfit():
    pass

def format_outfit_result():
    pass

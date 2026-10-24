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

def format_outfit(outfit:Outfit, wardrobe:list[Garment]) -> str:
    lines = []

    lines.append(f"{outfit.aesthetic.upper()} {'=' * (65 - len(outfit.aesthetic))}")
    for garment in outfit.garments:
        lines.append(f"  -{format_garment_id_name(wardrobe[garment.garment_id])}")
        lines.append(f"        {garment.styling_advice}")
    lines.append("")
    lines.append(f"  {outfit.explanation}")
    lines.append("")
    if outfit.missing:
        lines.append(f"  Consider: {outfit.missing}")
        lines.append("")

    return "\n".join(lines)

def format_outfit_result(outfit_result: OutfitResult, wardrobe: dict[Garment]) -> str | None:
    lines = []
    for outfit in outfit_result.outfits:
        lines.append(format_outfit(outfit, wardrobe))

    return "\n".join(lines) if lines else None

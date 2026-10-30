from enclothed.models import Garment, Outfit, OutfitResult, CATEGORY_ORDER
import textwrap

def format_garment_id_name(garment: Garment) -> str:
    return f"{garment.id:>3}  {garment.name}"

def format_garment_set(set_id: int, set_name: str | None) -> str:
    return f" (set ID {set_id}{': ' + set_name if set_name else ''})"

def format_list(wardrobe: list[Garment], wardrobe_sets: dict[int, str | None]) -> str:
    if not wardrobe:
        raise ValueError("no garments in list passed to format_list()")

    lines = []
    current_category = ""

    wardrobe = sorted(wardrobe, key=lambda garment: (CATEGORY_ORDER[garment.category], garment.name.casefold(), garment.id),)

    for garment in wardrobe:
        if garment.category != current_category:
            if current_category != "":
                lines.append("")
            current_category = garment.category
            lines.append(f"{garment.category.upper()} {'=' * (45 - len(garment.category))}")
        line = f"  {format_garment_id_name(garment)}"
        if garment.set_id is not None:
            line += format_garment_set(garment.set_id, wardrobe_sets[garment.set_id])
        lines.append(line)

    lines.append("")
    set_count = len({garment.set_id for garment in wardrobe if garment.set_id is not None})
    lines.append(f"{len(wardrobe)} garment{'s' if len(wardrobe) != 1 else ''} and {set_count} set{'s' if set_count != 1 else ''} found")

    return "\n".join(lines)

def format_new_garment(garment: Garment) -> str:
    return f"new garment added:\n  {format_garment_id_name(garment)}"

def format_outfit(outfit: Outfit, wardrobe: dict[int, Garment]) -> str:
    lines = []

    lines.append(f"{outfit.aesthetic.upper()} {'=' * (65 - len(outfit.aesthetic))}")

    for outfit_garment in outfit.garments:
        garment = wardrobe.get(outfit_garment.garment_id)
        if garment is None:
            label = f"{outfit_garment.garment_id:>3}  (not in wardrobe)"
        else:
            label = format_garment_id_name(garment)
        lines.append(f"  -{label}")
        if outfit_garment.styling_advice:
            lines.append(textwrap.fill(outfit_garment.styling_advice, width=80, initial_indent="        ", subsequent_indent="        "))

    lines.append("")
    lines.append(textwrap.fill(outfit.explanation, width=80, initial_indent="  ", subsequent_indent="  "))
    if outfit.missing:
        lines.append("")
        lines.append(textwrap.fill(f"Consider: {outfit.missing}", width=80, initial_indent="  ", subsequent_indent="  "))

    return "\n".join(lines)

def format_outfit_result(outfit_result: OutfitResult, wardrobe: dict[int, Garment]) -> str:
    lines = []
    for outfit in outfit_result.outfits:
        lines.append(format_outfit(outfit, wardrobe))

    return "\n\n".join(lines)

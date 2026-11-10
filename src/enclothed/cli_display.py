from enclothed.models import CLOSENESS_LABELS, Garment, LookMatchOut, LookTags, Outfit, OutfitResult, CATEGORY_ORDER
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

    title = outfit.aesthetic.upper() + (f" [{outfit.risk_tier}]" if outfit.risk_tier else "")
    lines.append(f"{title} {'=' * (65 - len(title))}")

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


def format_look(tags: LookTags, recreations: list[tuple[Outfit, list[LookMatchOut]]], wardrobe: dict[int, Garment]) -> str:
    """mimic: the look as the photos showed it, then each recreation piece by piece."""
    title = "LOOK: " + tags.title.upper() + (f" [{tags.silhouette}-line]" if tags.silhouette else "")
    lines = [f"{title} {'=' * max(3, 65 - len(title))}", textwrap.fill(tags.summary, width=80, initial_indent="  ", subsequent_indent="  ")]
    if not recreations:
        lines += ["", "  Nothing in your wardrobe could recreate this look."]

    for number, (outfit, matches) in enumerate(recreations, start=1):
        heading = f"RECREATION {number}: {outfit.aesthetic.upper()}"
        lines += ["", f"{heading} {'=' * max(3, 65 - len(heading))}"]
        stand_ins = set()
        for match in matches:
            piece = tags.pieces[match.piece - 1]
            lines.append(f"  {match.piece}. {piece.primary_color} {piece.subcategory} ({piece.role})")
            if match.garment_id is None:
                lines.append("       -> nothing owned")
            else:
                stand_ins.add(match.garment_id)
                lines.append(f"       -> {CLOSENESS_LABELS[match.closeness].lower():<6} {format_garment_id_name(wardrobe[match.garment_id]).strip()}")
            if match.note:
                lines.append(textwrap.fill(match.note, width=80, initial_indent="          ", subsequent_indent="          "))
        for extra in (g for g in outfit.garments if g.garment_id not in stand_ins):
            lines.append(f"  + {format_garment_id_name(wardrobe[extra.garment_id]).strip()}  (not in the photos)")
        lines += ["", textwrap.fill(outfit.explanation, width=80, initial_indent="  ", subsequent_indent="  ")]
        if outfit.missing:
            lines += ["", textwrap.fill(f"To finish the look: {outfit.missing}", width=80, initial_indent="  ", subsequent_indent="  ")]

    return "\n".join(lines)

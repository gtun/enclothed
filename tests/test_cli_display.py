# tests/test_cli_display.py
# The formatters are pure: fixed models in, a string out. No DB, no Claude.
# Each test picks one input shape Claude (or the DB) could produce and pins the layout.
from enclothed.cli_display import (
    format_garment_id_name,
    format_list,
    format_new_garment,
    format_outfit,
    format_outfit_result,
)
from enclothed.intake import TEST_GARMENT
from enclothed.models import Garment, Outfit, OutfitResult


def garment(id: int, category: str, subcategory: str, brand: str | None, color: str) -> Garment:
    """A copy of TEST_GARMENT with only the fields the formatters read changed."""
    return TEST_GARMENT.model_copy(update={
        "id": id,
        "category": category,
        "subcategory": subcategory,
        "brand": brand,
        "primary_color": color,
    })


def outfit(**fields) -> Outfit:
    """A small valid Outfit; override any field with a keyword."""
    data = {
        "aesthetic": "Test Look",
        "garments": [{"garment_id": 1, "styling_advice": "Wear it open."}],
        "explanation": "Short reason.",
        "missing": None,
    }
    data.update(fields)
    return Outfit.model_validate(data)


WARDROBE = {
    1: garment(1, "outerwear", "blouson", "nonnative", "black"),
    2: garment(2, "shoes", "derbies", "Camper", "black"),
}


# --- format_garment_id_name -------------------------------------------------

def test_id_is_right_aligned_to_width_3():
    assert format_garment_id_name(WARDROBE[1]) == "  1  nonnative black blouson"
    assert format_garment_id_name(garment(25, "shoes", "derbies", "Camper", "black")) == " 25  Camper black derbies"


# --- format_list -------------------------------------------------------------

def test_list_empty_returns_none():
    assert format_list([]) is None


def test_list_groups_sorts_and_skips_empty_categories():
    # Given out of order: shoes before tops, and two tops in reverse name order.
    garments = [
        garment(3, "shoes", "derbies", "Camper", "black"),
        garment(2, "top", "casual shirt", "Taylor Stitch", "cream"),
        garment(1, "top", "camp-collar shirt", "Old Joe Brand", "black"),
    ]
    expected = (
        "TOP ==========================================\n"
        "    1  Old Joe Brand black camp-collar shirt\n"
        "    2  Taylor Stitch cream casual shirt\n"
        "\n"
        "SHOES ========================================\n"
        "    3  Camper black derbies\n"
        "\n"
        "3 garments found"
    )
    assert format_list(garments) == expected


def test_list_sorts_names_case_insensitively():
    # Plain sorted() would put every capitalized brand before "nonnative".
    garments = [
        garment(1, "outerwear", "blouson", "UNUSED", "cream"),
        garment(2, "outerwear", "blouson", "nonnative", "black"),
        garment(3, "outerwear", "blouson", "Belstaff", "camel"),
    ]
    lines = format_list(garments).splitlines()
    garment_lines = lines[1:4]  # skip the header; stop before the blank line and count
    assert [line.split()[1] for line in garment_lines] == ["Belstaff", "nonnative", "UNUSED"]


def test_list_count_is_singular_for_one_garment():
    assert format_list([WARDROBE[1]]).endswith("\n\n1 garment found")


def test_list_count_is_plural_for_several_garments():
    assert format_list([WARDROBE[1], WARDROBE[2]]).endswith("\n\n2 garments found")


def test_list_count_covers_every_category():
    # Two tops and one pair of shoes: the count is the total, not the last group's size.
    garments = [
        garment(1, "top", "casual shirt", "Taylor Stitch", "cream"),
        garment(2, "top", "camp-collar shirt", "Old Joe Brand", "black"),
        garment(3, "shoes", "derbies", "Camper", "black"),
    ]
    assert format_list(garments).splitlines()[-1] == "3 garments found"


def test_list_does_not_mutate_input():
    garments = [WARDROBE[2], WARDROBE[1]]
    format_list(garments)
    assert garments == [WARDROBE[2], WARDROBE[1]]


# --- format_new_garment -------------------------------------------------------

def test_new_garment_message():
    assert format_new_garment(WARDROBE[1]) == "new garment added:\n    1  nonnative black blouson"


# --- format_outfit -------------------------------------------------------------

def test_outfit_layout():
    result = format_outfit(outfit(), WARDROBE)
    lines = result.splitlines()
    assert lines[0].startswith("TEST LOOK ")
    assert lines[1] == "  -  1  nonnative black blouson"
    assert lines[2] == "        Wear it open."
    assert lines[3] == ""
    assert lines[4] == "  Short reason."


def test_outfit_without_missing_has_no_consider_line():
    assert "Consider:" not in format_outfit(outfit(missing=None), WARDROBE)


def test_outfit_with_missing_has_consider_line():
    result = format_outfit(outfit(missing="A plain white tee."), WARDROBE)
    assert result.endswith("\n\n  Consider: A plain white tee.")


def test_outfit_skips_missing_styling_advice():
    result = format_outfit(outfit(garments=[{"garment_id": 1, "styling_advice": None}]), WARDROBE)
    lines = result.splitlines()
    assert lines[1] == "  -  1  nonnative black blouson"
    assert lines[2] == ""  # straight to the blank line before the explanation


def test_outfit_unknown_id_shows_placeholder():
    result = format_outfit(outfit(garments=[{"garment_id": 99, "styling_advice": "x"}]), WARDROBE)
    assert "  - 99  (not in wardrobe)" in result


def test_outfit_wraps_long_text_at_80_columns():
    long_text = "word " * 60
    result = format_outfit(outfit(explanation=long_text, missing=long_text), WARDROBE)
    assert all(len(line) <= 80 for line in result.splitlines())


# --- format_outfit_result ------------------------------------------------------

def test_outfits_separated_by_one_blank_line():
    result = OutfitResult(outfits=[outfit(aesthetic="First"), outfit(aesthetic="Second")])
    output = format_outfit_result(result, WARDROBE)
    assert "Short reason.\n\nSECOND " in output
    assert "\n\n\n" not in output
    assert not output.endswith("\n")

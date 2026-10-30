# tests/test_cli_display.py
# The formatters are pure: fixed models in, a string out. No DB, no Claude.
# Each test picks one input shape Claude (or the DB) could produce and pins the layout.
import pytest

from enclothed.cli_display import (
    format_garment_id_name,
    format_garment_set,
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


# --- format_garment_set ------------------------------------------------------

def test_set_label_without_name():
    assert format_garment_set(3, None) == " (set ID 3)"


def test_set_label_with_name():
    assert format_garment_set(3, "Burberry suit") == " (set ID 3: Burberry suit)"


# --- format_list -------------------------------------------------------------

def in_set(garment: Garment, set_id: int) -> Garment:
    """A copy of a garment that belongs to a set."""
    return garment.model_copy(update={"set_id": set_id})


def test_list_empty_raises():
    # main checks for an empty list first, so reaching here is a bug.
    with pytest.raises(ValueError):
        format_list([], {})


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
        "3 garments and 0 sets found"
    )
    assert format_list(garments, {}) == expected


def test_list_sorts_names_case_insensitively():
    # Plain sorted() would put every capitalized brand before "nonnative".
    garments = [
        garment(1, "outerwear", "blouson", "UNUSED", "cream"),
        garment(2, "outerwear", "blouson", "nonnative", "black"),
        garment(3, "outerwear", "blouson", "Belstaff", "camel"),
    ]
    lines = format_list(garments, {}).splitlines()
    garment_lines = lines[1:4]  # skip the header; stop before the blank line and count
    assert [line.split()[1] for line in garment_lines] == ["Belstaff", "nonnative", "UNUSED"]


def test_list_count_is_singular_for_one_garment():
    assert format_list([WARDROBE[1]], {}).endswith("\n\n1 garment and 0 sets found")


def test_list_count_is_plural_for_several_garments():
    assert format_list([WARDROBE[1], WARDROBE[2]], {}).endswith("\n\n2 garments and 0 sets found")


def test_list_count_covers_every_category():
    # Two tops and one pair of shoes: the count is the total, not the last group's size.
    garments = [
        garment(1, "top", "casual shirt", "Taylor Stitch", "cream"),
        garment(2, "top", "camp-collar shirt", "Old Joe Brand", "black"),
        garment(3, "shoes", "derbies", "Camper", "black"),
    ]
    assert format_list(garments, {}).splitlines()[-1] == "3 garments and 0 sets found"


def test_list_labels_only_set_members():
    # A suit jacket in a named set, its trousers in the same set, and shoes in no set.
    garments = [
        in_set(garment(1, "outerwear", "suit jacket", "Burberry", "slate blue"), 7),
        in_set(garment(2, "bottom", "dress trousers", "Burberry", "slate blue"), 7),
        garment(3, "shoes", "derbies", "Camper", "black"),
    ]
    lines = format_list(garments, {7: "Burberry suit"}).splitlines()
    # Category order puts bottoms before outerwear.
    assert lines[1] == "    2  Burberry slate blue dress trousers (set ID 7: Burberry suit)"
    assert lines[4] == "    1  Burberry slate blue suit jacket (set ID 7: Burberry suit)"
    assert lines[7] == "    3  Camper black derbies"


def test_list_unnamed_set_shows_id_only():
    garments = [in_set(garment(1, "outerwear", "suit jacket", "Zara Man", "navy"), 4)]
    assert format_list(garments, {4: None}).splitlines()[1] == "    1  Zara Man navy suit jacket (set ID 4)"


def test_list_set_count_is_singular_for_one_set():
    # Two garments, one set: the set is counted once.
    garments = [
        in_set(garment(1, "outerwear", "suit jacket", "Zara Man", "navy"), 4),
        in_set(garment(2, "bottom", "dress trousers", "Zara Man", "navy"), 4),
    ]
    assert format_list(garments, {4: None}).splitlines()[-1] == "2 garments and 1 set found"


def test_list_counts_only_sets_in_the_listed_garments():
    # list -c shoes: the wardrobe has two sets, but no listed garment belongs to one.
    garments = [garment(3, "shoes", "derbies", "Camper", "black")]
    sets = {4: None, 7: "Burberry suit"}
    assert format_list(garments, sets).splitlines()[-1] == "1 garment and 0 sets found"


def test_list_does_not_mutate_input():
    garments = [WARDROBE[2], WARDROBE[1]]
    format_list(garments, {})
    assert garments == [WARDROBE[2], WARDROBE[1]]


def test_list_missing_set_raises():
    # The foreign key makes this impossible in real data; if it happens, fail loudly.
    garments = [in_set(WARDROBE[1], 99)]
    with pytest.raises(KeyError):
        format_list(garments, {})


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

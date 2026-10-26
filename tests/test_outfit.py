# tests/test_outfit.py
# Covers what outfit.py does today: trimming the wardrobe for the prompt, building
# the context, logging, and validating Claude's reply. Test mode (is_test=True)
# fakes only the LLM (ADR-020), so get_outfits runs for real with no client and
# no tokens. Validation is pure, so its tests build small outfits and a fake
# wardrobe by hand: they test the checks, not Claude.
import json

from enclothed import config
from enclothed.intake import TEST_GARMENT
from enclothed.models import Outfit, OutfitResult
from enclothed.outfit import (
    OUTFIT_INCLUDE_FIELDS,
    TEST_OUTFITS,
    count_categories,
    get_outfits,
    validate_outfit,
    validate_outfits,
    wardrobe_for_prompt,
)
from enclothed.db import init_db

WARDROBE = {
    1: TEST_GARMENT.model_copy(update={"id": 1}),
    2: TEST_GARMENT.model_copy(update={"id": 2, "category": "shoes", "subcategory": "derbies", "brand": "Camper"}),
}

def run_test_mode(tmp_path, anchors, prompt="dinner downtown"):
    """get_outfits in test mode; returns (result, the one log entry)."""
    db_path = tmp_path / "test.db"
    init_db(db_path, config.SCHEMA_PATH)
    log_path = tmp_path / "outfit_log.jsonl"
    result = get_outfits(db_path, WARDROBE, anchors, log_path, None, prompt, True)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    return result, json.loads(lines[0])

# --- wardrobe_for_prompt --------------------------------------------------------

def test_prompt_wardrobe_keeps_only_whitelisted_fields():
    trimmed = wardrobe_for_prompt(WARDROBE)
    assert set(trimmed) == {1, 2}
    for fields in trimmed.values():
        assert set(fields) <= OUTFIT_INCLUDE_FIELDS


def test_prompt_wardrobe_never_sends_private_or_system_fields():
    fields = wardrobe_for_prompt(WARDROBE)[1]
    for private in ("notes", "label_text", "country_of_origin", "id", "wear_count", "last_worn", "date_added"):
        assert private not in fields


def test_prompt_wardrobe_does_not_mutate_input():
    before = {i: g.model_copy(deep=True) for i, g in WARDROBE.items()}
    wardrobe_for_prompt(WARDROBE)
    assert WARDROBE == before


# --- get_outfits (test mode) ------------------------------------------------------

def test_test_mode_returns_canned_result(tmp_path):
    result, _ = run_test_mode(tmp_path, [1])
    assert isinstance(result, OutfitResult)
    assert result == TEST_OUTFITS


def test_test_mode_logs_one_entry_with_null_usage(tmp_path):
    _, entry = run_test_mode(tmp_path, [1])
    assert entry["anchors"] == [1]
    assert entry["usage"] is None
    assert entry["result"] == TEST_OUTFITS.model_dump(mode="json")
    assert "timestamp" in entry


def test_context_has_wardrobe_anchors_and_request_in_order(tmp_path):
    _, entry = run_test_mode(tmp_path, [1], prompt="dinner downtown")
    context = entry["context"]
    assert context.index("<wardrobe>") < context.index("<anchors>") < context.index("<request>")
    assert "1: nonnative x UNDERCOVER black blouson" in context
    assert "<request>dinner downtown</request>" in context


def test_context_omits_anchors_section_when_none(tmp_path):
    _, entry = run_test_mode(tmp_path, None)
    assert entry["anchors"] is None
    assert "<anchors>" not in entry["context"]


def test_context_wardrobe_is_valid_json(tmp_path):
    _, entry = run_test_mode(tmp_path, None)
    context = entry["context"]
    start = context.index("<wardrobe>") + len("<wardrobe>")
    end = context.index("</wardrobe>")
    sent = json.loads(context[start:end])
    assert set(sent) == {"1", "2"}  # JSON object keys are always strings
    assert sent["2"]["subcategory"] == "derbies"


def test_log_records_problems_as_a_json_list(tmp_path):
    # WARDROBE has only ids 1 and 2, so TEST_OUTFITS' other ids are unknown here.
    _, entry = run_test_mode(tmp_path, [1])
    assert isinstance(entry["problems"], list)
    assert any("unknown garment id(s)" in p for p in entry["problems"])


# --- validation -------------------------------------------------------------------
# A fake wardrobe with one garment per role. Only category matters to the checks.

def garment_in(category, garment_id):
    return TEST_GARMENT.model_copy(update={"id": garment_id, "category": category})


TOP, TOP_2, BOTTOM, ONE_PIECE, SHOES, OUTER, ACCESSORY = 1, 2, 3, 4, 5, 6, 7

VALIDATION_WARDROBE = {
    TOP: garment_in("top", TOP),
    TOP_2: garment_in("top", TOP_2),
    BOTTOM: garment_in("bottom", BOTTOM),
    ONE_PIECE: garment_in("one-piece", ONE_PIECE),
    SHOES: garment_in("shoes", SHOES),
    OUTER: garment_in("outerwear", OUTER),
    ACCESSORY: garment_in("accessory", ACCESSORY),
}


def outfit_of(*garment_ids):
    return Outfit(
        aesthetic="test",
        explanation="test",
        garments=[{"garment_id": i, "styling_advice": "test"} for i in garment_ids],
    )


def result_of(count):
    """An OutfitResult with `count` valid outfits."""
    return OutfitResult(outfits=[outfit_of(TOP, BOTTOM, SHOES) for _ in range(count)])


# count_categories

def test_count_categories_counts_every_category():
    counts = count_categories({TOP, TOP_2, BOTTOM, SHOES}, VALIDATION_WARDROBE)
    assert counts == {"top": 2, "bottom": 1, "one-piece": 0, "outerwear": 0, "shoes": 1, "accessory": 0}


def test_count_categories_empty_gives_all_zeros():
    counts = count_categories(set(), VALIDATION_WARDROBE)
    assert set(counts.values()) == {0}


# validate_outfit: valid shapes (coverage is minimums only, ADR-039)

def test_top_bottom_shoes_is_valid():
    assert validate_outfit(outfit_of(TOP, BOTTOM, SHOES), VALIDATION_WARDROBE, None) == []


def test_one_piece_and_shoes_is_valid():
    assert validate_outfit(outfit_of(ONE_PIECE, SHOES), VALIDATION_WARDROBE, None) == []


def test_one_piece_over_top_and_bottom_is_valid():
    assert validate_outfit(outfit_of(ONE_PIECE, TOP, BOTTOM, SHOES), VALIDATION_WARDROBE, None) == []


def test_layered_tops_outerwear_and_accessory_are_valid():
    outfit = outfit_of(TOP, TOP_2, BOTTOM, SHOES, OUTER, ACCESSORY)
    assert validate_outfit(outfit, VALIDATION_WARDROBE, None) == []


def test_present_anchors_are_valid():
    assert validate_outfit(outfit_of(TOP, BOTTOM, SHOES), VALIDATION_WARDROBE, [TOP, SHOES]) == []


# validate_outfit: one problem each

def test_missing_anchor_is_reported():
    problems = validate_outfit(outfit_of(TOP, BOTTOM, SHOES), VALIDATION_WARDROBE, [OUTER])
    assert problems == [f"anchor(s) [{OUTER}] missing"]


def test_duplicate_garment_is_reported():
    problems = validate_outfit(outfit_of(TOP, BOTTOM, BOTTOM, SHOES), VALIDATION_WARDROBE, None)
    assert problems == ["duplicate garments found in outfit"]


def test_unknown_id_is_reported_without_crashing():
    problems = validate_outfit(outfit_of(TOP, BOTTOM, SHOES, 999), VALIDATION_WARDROBE, None)
    assert problems == ["unknown garment id(s) [999]"]


def test_top_without_bottom_is_not_covered():
    problems = validate_outfit(outfit_of(TOP, SHOES), VALIDATION_WARDROBE, None)
    assert problems == ["body is not covered by a top and a bottom or a one-piece"]


def test_bottom_without_top_is_not_covered():
    problems = validate_outfit(outfit_of(BOTTOM, SHOES), VALIDATION_WARDROBE, None)
    assert problems == ["body is not covered by a top and a bottom or a one-piece"]


def test_missing_shoes_is_reported():
    problems = validate_outfit(outfit_of(TOP, BOTTOM), VALIDATION_WARDROBE, None)
    assert problems == ["outfit has no footwear suggestion"]


def test_unknown_id_does_not_count_toward_coverage():
    # 999 might "be" shoes, but code can't know that, so shoes are still missing.
    problems = validate_outfit(outfit_of(TOP, BOTTOM, 999), VALIDATION_WARDROBE, None)
    assert "outfit has no footwear suggestion" in problems


def test_several_problems_are_all_reported():
    problems = validate_outfit(outfit_of(TOP, TOP, 999), VALIDATION_WARDROBE, [OUTER])
    assert len(problems) == 5  # anchor, duplicate, unknown, coverage, shoes


# validate_outfits: the whole reply

def test_valid_result_has_no_problems():
    assert validate_outfits(result_of(config.MIN_OUTFIT_SUGGESTIONS), VALIDATION_WARDROBE, None) == []


def test_too_few_outfits_is_reported():
    problems = validate_outfits(result_of(config.MIN_OUTFIT_SUGGESTIONS - 1), VALIDATION_WARDROBE, None)
    assert len(problems) == 1
    assert "outfit(s) returned" in problems[0]


def test_too_many_outfits_is_reported():
    problems = validate_outfits(result_of(config.MAX_OUTFIT_SUGGESTIONS + 1), VALIDATION_WARDROBE, None)
    assert len(problems) == 1
    assert "outfit(s) returned" in problems[0]


def test_problems_are_numbered_from_one():
    result = OutfitResult(outfits=[outfit_of(TOP, BOTTOM, SHOES), outfit_of(TOP, BOTTOM)])
    assert validate_outfits(result, VALIDATION_WARDROBE, None) == ["Outfit 2: outfit has no footwear suggestion"]


def test_validate_outfits_does_not_mutate_input():
    result = result_of(2)
    before = result.model_copy(deep=True)
    validate_outfits(result, VALIDATION_WARDROBE, [TOP])
    assert result == before

# tests/test_outfit.py
# Covers what outfit.py does today: trimming the wardrobe for the prompt, building
# the context, logging, and validating Claude's reply. Test mode (is_test=True)
# fakes only the LLM (ADR-020), so get_outfits runs for real with no client and
# no tokens. Validation is pure, so its tests build small outfits and a fake
# wardrobe by hand: they test the checks, not Claude.
import json
import sqlite3
from contextlib import closing
from enclothed import outfit as outfit_module
from enclothed.models import Outfit, OutfitResult, TokenUsage

from enclothed import config
from enclothed.intake import TEST_GARMENT
from enclothed.outfit import (
    OUTFIT_INCLUDE_FIELDS,
    TEST_OUTFITS,
    count_categories,
    fill_single_tier,
    get_outfits,
    options_text,
    tier_plan,
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
    init_db(db_path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    log_path = tmp_path / "outfit_log.jsonl"
    result = get_outfits(db_path, 1, WARDROBE, anchors, log_path, None, prompt, True)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    return result, json.loads(lines[0])

# --- wardrobe_for_prompt --------------------------------------------------------

def test_prompt_wardrobe_keeps_only_whitelisted_fields():
    trimmed = wardrobe_for_prompt(WARDROBE)
    assert set(trimmed) == {1, 2}
    for fields in trimmed.values():
        assert set(fields) - {"layer"} <= OUTFIT_INCLUDE_FIELDS


def test_prompt_wardrobe_adds_each_pieces_layer():
    records = wardrobe_for_prompt({
        1: TEST_GARMENT.model_copy(update=dict(category="top", subcategory="t-shirt")),
        2: TEST_GARMENT.model_copy(update=dict(category="top", subcategory="cardigan")),
        3: TEST_GARMENT.model_copy(update=dict(category="outerwear", subcategory="parka")),
        4: TEST_GARMENT.model_copy(update=dict(category="bottom", subcategory="jeans")),
    })
    assert [records[i].get("layer") for i in (1, 2, 3, 4)] == ["base", "mid", "outer", None]


def test_prompt_wardrobe_sends_the_new_attributes():
    garment = TEST_GARMENT.model_copy(update=dict(category="top", subcategory="t-shirt", fabric_type="jersey", shape="boxy", hem="hip",
                           fabric_weight="mid", sleeve="short", statement="basic"))
    record = wardrobe_for_prompt({1: garment})[1]
    assert {key: record[key] for key in ("fabric_type", "shape", "hem", "fabric_weight", "sleeve", "statement")} == {
        "fabric_type": "jersey", "shape": "boxy", "hem": "hip", "fabric_weight": "mid", "sleeve": "short", "statement": "basic",
    }


def test_prompt_wardrobe_never_sends_private_or_system_fields():
    fields = wardrobe_for_prompt(WARDROBE)[1]
    for private in ("notes", "label_text", "country_of_origin", "id", "date_added"):
        assert private not in fields


def test_prompt_wardrobe_sends_set_id_when_garment_is_in_a_set():
    in_a_set = {1: TEST_GARMENT.model_copy(update={"id": 1, "set_id": 7})}
    assert wardrobe_for_prompt(in_a_set)[1]["set_id"] == 7


def test_prompt_wardrobe_leaves_out_empty_fields():
    # exclude_none: a garment with no set and no formality sends neither key
    not_in_a_set = {1: TEST_GARMENT.model_copy(update={"id": 1, "set_id": None, "formality": None})}
    fields = wardrobe_for_prompt(not_in_a_set)[1]
    assert "set_id" not in fields
    assert "formality" not in fields


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


def test_test_mode_does_not_write_to_db(tmp_path):
    # Every TEST_OUTFITS outfit has unknown ids against WARDROBE (only ids 1 and 2),
    # so under the save rule nothing reaches the DB, but the reply is still logged.
    _, entry = run_test_mode(tmp_path, [1])
    with closing(sqlite3.connect(tmp_path / "test.db")) as conn:
        assert conn.execute("SELECT COUNT(*) FROM outfits").fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM outfit_garments").fetchone() == (0,)
    assert entry["result"] == TEST_OUTFITS.model_dump(mode="json")


# --- validation -------------------------------------------------------------------
# A fake wardrobe with one garment per role. Only category matters to the checks.

def garment_in(category, garment_id):
    return TEST_GARMENT.model_copy(update={"id": garment_id, "category": category})


TOP, TOP_2, BOTTOM, ONE_PIECE, SHOES, OUTER, ACCESSORY, SHOES_2 = 1, 2, 3, 4, 5, 6, 7, 8

VALIDATION_WARDROBE = {
    TOP: garment_in("top", TOP),
    TOP_2: garment_in("top", TOP_2),
    BOTTOM: garment_in("bottom", BOTTOM),
    ONE_PIECE: garment_in("one-piece", ONE_PIECE),
    SHOES: garment_in("shoes", SHOES),
    OUTER: garment_in("outerwear", OUTER),
    ACCESSORY: garment_in("accessory", ACCESSORY),
    SHOES_2: garment_in("shoes", SHOES_2),
}


def outfit_of(*garment_ids, tier=None):
    return Outfit(
        aesthetic="test",
        explanation="test",
        garments=[{"garment_id": i, "styling_advice": "test"} for i in garment_ids],
        risk_tier=tier,
    )


def result_of(count, tier="safe"):
    """An OutfitResult with `count` valid outfits, all at one tier."""
    return OutfitResult(outfits=[outfit_of(TOP, BOTTOM, SHOES, tier=tier) for _ in range(count)])


def result_of_tiers(*tiers):
    """An OutfitResult with one valid outfit per tier given."""
    return OutfitResult(outfits=[outfit_of(TOP, BOTTOM, SHOES, tier=t) for t in tiers])


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


def test_two_pairs_of_shoes_is_reported():
    problems = validate_outfit(outfit_of(TOP, BOTTOM, SHOES, SHOES_2), VALIDATION_WARDROBE, None)
    assert problems == ["outfit suggests multiple shoes"]


def test_several_problems_are_all_reported():
    problems = validate_outfit(outfit_of(TOP, TOP, 999), VALIDATION_WARDROBE, [OUTER])
    assert len(problems) == 5  # anchor, duplicate, unknown, coverage, shoes


# validate_outfits: the whole reply -> (problems, valid outfits)

def test_valid_result_has_no_problems():
    result = result_of_tiers("safe", "stretch", "bold")
    problems, valid = validate_outfits(result, VALIDATION_WARDROBE, None, tier_plan(3, None))
    assert problems == []
    assert valid == result.outfits


def test_without_a_plan_count_and_tiers_are_not_checked():
    problems, _ = validate_outfits(result_of(7, tier=None), VALIDATION_WARDROBE, None)
    assert problems == []


def test_too_few_outfits_is_reported():
    problems, _ = validate_outfits(result_of(2), VALIDATION_WARDROBE, None, tier_plan(3, "safe"))
    assert problems == ["2 outfit(s) returned, expected 3"]


def test_too_many_outfits_is_reported():
    problems, _ = validate_outfits(result_of(4), VALIDATION_WARDROBE, None, tier_plan(3, "safe"))
    assert problems == ["4 outfit(s) returned, expected 3"]


def test_wrong_tier_mix_is_reported():
    problems, _ = validate_outfits(result_of_tiers("safe", "safe", "bold"), VALIDATION_WARDROBE, None, tier_plan(3, None))
    assert problems == ["tiers returned {'bold': 1, 'safe': 2}, expected {'bold': 1, 'safe': 1, 'stretch': 1}"]


def test_blank_tier_counts_as_untiered():
    problems, _ = validate_outfits(result_of_tiers("safe", "stretch", None), VALIDATION_WARDROBE, None, tier_plan(3, None))
    assert len(problems) == 1
    assert "'untiered': 1" in problems[0]


def test_tier_problem_does_not_drop_valid_outfits():
    result = result_of(3, tier="safe")
    problems, valid = validate_outfits(result, VALIDATION_WARDROBE, None, tier_plan(3, "bold"))
    assert len(problems) == 1
    assert valid == result.outfits


def test_problems_are_numbered_from_one():
    result = OutfitResult(outfits=[outfit_of(TOP, BOTTOM, SHOES), outfit_of(TOP, BOTTOM)])
    problems, _ = validate_outfits(result, VALIDATION_WARDROBE, None)
    assert problems == ["Outfit 2: outfit has no footwear suggestion"]


def test_each_problem_is_its_own_line():
    # Two problems in one outfit -> two log lines, each with its own prefix
    # (not one line holding a Python list).
    result = OutfitResult(outfits=[outfit_of(TOP, BOTTOM, SHOES), outfit_of(TOP, 999)])
    problems, _ = validate_outfits(result, VALIDATION_WARDROBE, None)
    assert problems == [
        "Outfit 2: unknown garment id(s) [999]",
        "Outfit 2: body is not covered by a top and a bottom or a one-piece",
        "Outfit 2: outfit has no footwear suggestion",
    ]


def test_valid_keeps_only_clean_outfits_in_order():
    good_1 = outfit_of(TOP, BOTTOM, SHOES)
    bad = outfit_of(TOP, BOTTOM)
    good_2 = outfit_of(ONE_PIECE, SHOES)
    _, valid = validate_outfits(OutfitResult(outfits=[good_1, bad, good_2]), VALIDATION_WARDROBE, None)
    assert valid == [good_1, good_2]


def test_valid_is_empty_when_every_outfit_has_problems():
    result = OutfitResult(outfits=[outfit_of(TOP, BOTTOM), outfit_of(BOTTOM, SHOES)])
    problems, valid = validate_outfits(result, VALIDATION_WARDROBE, None)
    assert len(problems) == 2
    assert valid == []


def test_count_problem_does_not_drop_valid_outfits():
    # Gary's rule (10-26): the count is reported, but every clean outfit is still kept.
    result = result_of(4)
    problems, valid = validate_outfits(result, VALIDATION_WARDROBE, None, tier_plan(3, "safe"))
    assert len(problems) == 1
    assert len(valid) == 4


def test_validate_outfits_does_not_mutate_input():
    result = result_of(2)
    before = result.model_copy(deep=True)
    validate_outfits(result, VALIDATION_WARDROBE, [TOP])
    assert result == before

# --- prompt caching ------------------------------------------------------------
# Real-mode get_outfits with recommend_outfits replaced by a fake that records the
# content blocks it was given. No client, no tokens.

FAKE_USAGE = TokenUsage(
    model="test-model",
    input_tokens=40,
    output_tokens=1500,
    cache_creation_input_tokens=0,
    cache_read_input_tokens=41796,
)


def run_real_mode(tmp_path, monkeypatch, anchors=None, **kwargs):
    """get_outfits with a fake recommend_outfits; returns (blocks sent, the one log entry).
    kwargs go straight to get_outfits (e.g. caching=True), so leaving them out
    tests the default."""
    sent = {}

    def fake_recommend_outfits(client, context, language="en-US"):
        sent["blocks"] = context
        return TEST_OUTFITS, FAKE_USAGE

    # Patch the name outfit.py imported, not enclothed.llm.recommend_outfits.
    monkeypatch.setattr(outfit_module, "recommend_outfits", fake_recommend_outfits)

    tmp_path.mkdir(parents=True, exist_ok=True)  # callers may pass a subfolder
    db_path = tmp_path / "test.db"
    init_db(db_path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    log_path = tmp_path / "outfit_log.jsonl"
    get_outfits(db_path, 1, WARDROBE, anchors, log_path, None, "dinner downtown", False, **kwargs)
    return sent["blocks"], json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])


def test_caching_marks_only_the_wardrobe_block(tmp_path, monkeypatch):
    blocks, _ = run_real_mode(tmp_path, monkeypatch, anchors=[1], caching=True)
    assert blocks[0]["text"].startswith("<wardrobe>")
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    # Anchors and request change between calls, so they must stay after the breakpoint.
    assert all("cache_control" not in block for block in blocks[1:])


def test_no_caching_sends_no_breakpoint(tmp_path, monkeypatch):
    blocks, _ = run_real_mode(tmp_path, monkeypatch, anchors=[1], caching=False)
    assert all("cache_control" not in block for block in blocks)


def test_caching_is_on_by_default(tmp_path, monkeypatch):
    blocks, _ = run_real_mode(tmp_path, monkeypatch, anchors=[1])
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert all("cache_control" not in block for block in blocks[1:])


def test_blocks_are_wardrobe_anchors_request_in_order(tmp_path, monkeypatch):
    blocks, _ = run_real_mode(tmp_path, monkeypatch, anchors=[1], caching=True)
    assert len(blocks) == 4
    assert "<anchors>" in blocks[1]["text"]
    assert blocks[2]["text"] == "<request>dinner downtown</request>"
    assert blocks[3]["text"].startswith("<options>")


def test_no_anchors_means_no_anchors_block(tmp_path, monkeypatch):
    # The API rejects empty text blocks, so the anchors block must be left out, not empty.
    blocks, _ = run_real_mode(tmp_path, monkeypatch, anchors=None, caching=True)
    assert len(blocks) == 3
    assert all(block["text"] for block in blocks)


def test_log_context_is_the_same_string_with_or_without_caching(tmp_path, monkeypatch):
    _, cached = run_real_mode(tmp_path / "a", monkeypatch, anchors=[1], caching=True)
    _, uncached = run_real_mode(tmp_path / "b", monkeypatch, anchors=[1], caching=False)
    assert isinstance(cached["context"], str)
    assert cached["context"] == uncached["context"]
    assert "cache_control" not in cached["context"]


def test_log_records_cache_token_counts(tmp_path, monkeypatch):
    _, entry = run_real_mode(tmp_path, monkeypatch, anchors=[1], caching=True)
    assert entry["usage"]["cache_creation_input_tokens"] == 0
    assert entry["usage"]["cache_read_input_tokens"] == 41796


# --- risk tiers (#92) -----------------------------------------------------------

def test_tier_plan_spreads_the_count_safe_first():
    assert [tuple(tier_plan(n, None).values()) for n in range(1, 6)] == [
        (1, 0, 0), (1, 1, 0), (1, 1, 1), (2, 1, 1), (2, 2, 1),
    ]


def test_tier_plan_puts_every_outfit_at_the_chosen_tier():
    assert tier_plan(4, "bold") == {"safe": 0, "stretch": 0, "bold": 4}


def test_tier_plan_rejects_counts_out_of_range():
    import pytest
    for bad in (config.MIN_OUTFIT_COUNT - 1, config.MAX_OUTFIT_COUNT + 1):
        with pytest.raises(ValueError):
            tier_plan(bad, None)


def test_options_text_names_the_total_and_leaves_out_empty_tiers():
    assert options_text(tier_plan(2, None)) == "<options>\nSuggest exactly 2 outfits: 1 safe, 1 stretch.\n</options>"
    assert "1 outfit:" in options_text(tier_plan(1, "bold"))


def test_options_block_follows_the_request(tmp_path):
    _, entry = run_test_mode(tmp_path, None)
    context = entry["context"]
    assert context.index("<request>") < context.index("<options>")
    assert "Suggest exactly 3 outfits: 1 safe, 1 stretch, 1 bold." in context


def test_fill_single_tier_fills_blanks_when_one_tier_was_asked():
    result = OutfitResult(outfits=[outfit_of(TOP, tier=None), outfit_of(TOP, tier="safe")])
    filled = fill_single_tier(result, tier_plan(2, "bold"))
    assert [o.risk_tier for o in filled.outfits] == ["bold", "safe"]
    assert result.outfits[0].risk_tier is None   # the input is left alone


def test_fill_single_tier_leaves_a_mix_alone():
    result = OutfitResult(outfits=[outfit_of(TOP, tier=None)])
    assert fill_single_tier(result, tier_plan(3, None)) is result


def test_saved_outfits_keep_their_tier(tmp_path, monkeypatch):
    from enclothed.db import insert_garment, select_all_outfits, select_owned_garments
    db_path = tmp_path / "test.db"
    init_db(db_path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    pieces = (("top", "t-shirt"), ("bottom", "jeans"), ("shoes", "derbies"))
    ids = [insert_garment(db_path, 1, TEST_GARMENT.model_copy(update={"category": c, "subcategory": sub})) for c, sub in pieces]
    wardrobe = {g.id: g for g in select_owned_garments(db_path, 1)}
    reply = OutfitResult(outfits=[outfit_of(*ids, tier=t) for t in ("safe", "stretch", "bold")])
    monkeypatch.setattr(outfit_module, "recommend_outfits", lambda client, context, language: (reply, TokenUsage(model="m", input_tokens=1, output_tokens=1)))
    outfit_module.generate_outfits(db_path, 1, wardrobe, None, tmp_path / "log.jsonl", object(), "dinner", False)
    assert [o["risk_tier"] for o in select_all_outfits(db_path, 1)] == ["safe", "stretch", "bold"]

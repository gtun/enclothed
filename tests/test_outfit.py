# tests/test_outfit.py
# Covers what outfit.py does today: trimming the wardrobe for the prompt, building
# the context, and logging. Test mode (is_test=True) fakes only the LLM (ADR-020),
# so get_outfits runs for real with no client and no tokens.
# Step 4 validation tests go here once validate_outfits exists.
import json

from enclothed.intake import TEST_GARMENT
from enclothed.models import OutfitResult
from enclothed.outfit import OUTFIT_INCLUDE_FIELDS, TEST_OUTFITS, get_outfits, wardrobe_for_prompt

WARDROBE = {
    1: TEST_GARMENT.model_copy(update={"id": 1}),
    2: TEST_GARMENT.model_copy(update={"id": 2, "category": "shoes", "subcategory": "derbies", "brand": "Camper"}),
}


def run_test_mode(tmp_path, anchors, prompt="dinner downtown"):
    """get_outfits in test mode; returns (result, the one log entry)."""
    log_path = tmp_path / "outfit_log.jsonl"
    result = get_outfits(WARDROBE, anchors, log_path, None, prompt, True)
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

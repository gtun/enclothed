# eval-tags: choosing garments, comparing a re-tag with the saved record, and the files a run writes.
# Runs use test mode (canned tags, no client) or a fake tag_photos; none make an API call.
import json

import pytest
from PIL import Image

from enclothed import config, db, photos, tag_evals
from enclothed.intake import TEST_GARMENT
from enclothed.llm import ServiceError, UnusableResponse
from enclothed.models import Fiber, MaterialPart, PhotoTag, TaggingResult, TokenUsage


@pytest.fixture
def garments_dir(tmp_path, monkeypatch):
    folder = tmp_path / "garments"
    monkeypatch.setattr(photos, "GARMENTS_DIR", folder)
    return folder


@pytest.fixture
def owner_db(tmp_path):
    path = tmp_path / "enclothed.db"
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    return path


def add(db_path, garments_dir, garment=TEST_GARMENT, roles=("front", "label")):
    garment_id = db.insert_garment(db_path, 1, garment.model_copy())
    folder = garments_dir / str(garment_id)
    folder.mkdir(parents=True)
    for role in roles:
        Image.new("RGB", (20, 20), "navy").save(folder / f"{role}_00.jpg")
    return garment_id


def rows_of(out):
    return [json.loads(line) for line in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]


def run(owner_db, tmp_path, ids=None, limit=12, runs=1):
    return tag_evals.run("v1", runs, 1, owner_db, ids, limit, True, tmp_path / "evals")


# --- choosing garments ----------------------------------------------------------------------

def test_garments_are_spread_across_categories(owner_db, garments_dir):
    tops = [add(owner_db, garments_dir, TEST_GARMENT.model_copy(update={"category": "top", "subcategory": "henley"})) for _ in range(3)]
    shoes = [add(owner_db, garments_dir, TEST_GARMENT.model_copy(update={"category": "shoes", "subcategory": "chelsea boots"})) for _ in range(2)]
    chosen = tag_evals.choose_garments(db.select_owned_garments(owner_db, 1), None, 4)
    assert [g.id for g in chosen] == [tops[0], shoes[0], tops[1], shoes[1]]


def test_garments_without_photos_are_left_out(owner_db, garments_dir):
    with_photos = add(owner_db, garments_dir)
    add(owner_db, garments_dir, roles=())
    assert [g.id for g in tag_evals.choose_garments(db.select_owned_garments(owner_db, 1), None, 12)] == [with_photos]


def test_named_garments_must_exist_with_photos(owner_db, garments_dir):
    no_photos = add(owner_db, garments_dir, roles=())
    with pytest.raises(ValueError, match=str(no_photos)):
        tag_evals.choose_garments(db.select_owned_garments(owner_db, 1), [no_photos], 12)


def test_saved_roles_come_from_file_names(tmp_path):
    names = ["back_00.jpg", "front_00.jpg", "label_01.jpg", "url_0.jpg"]
    assert tag_evals.saved_roles([tmp_path / n for n in names]) == ["back", "front", "label", "other"]


# --- comparing ------------------------------------------------------------------------------

def test_an_identical_tag_matches_every_field_the_record_fills():
    results = tag_evals.compare(TEST_GARMENT, TEST_GARMENT)
    assert set(results) == set(tag_evals.SCORED_FIELDS) | {"formality ±1", "warmth ±1"}
    assert {outcome for field, outcome in results.items() if getattr(TEST_GARMENT, field.split(" ")[0]) not in (None, [])} == {tag_evals.MATCH}


def test_differences_are_found_field_by_field():
    tagged = TEST_GARMENT.model_copy(update={"primary_color": "navy", "formality": 3, "fit": None})
    results = tag_evals.compare(TEST_GARMENT.model_copy(update={"fit": "regular"}), tagged)
    assert results["primary_color"] == tag_evals.DIFFER
    assert results["fit"] == tag_evals.DIFFER            # the record has it, the re-tag left it blank
    assert results["formality"] == tag_evals.DIFFER
    assert results["formality ±1"] == tag_evals.MATCH    # 2 against 3
    assert results["subcategory"] == tag_evals.MATCH


def test_a_blank_in_the_record_isnt_scored():
    results = tag_evals.compare(TEST_GARMENT.model_copy(update={"hem": None}), TEST_GARMENT.model_copy(update={"hem": "hip"}))
    assert results["hem"] == tag_evals.SAVED_BLANK


def test_colors_compare_as_sets_and_text_ignores_case():
    saved = TEST_GARMENT.model_copy(update={"secondary_colors": ["white", "grey"], "brand": "Engineered Garments"})
    tagged = TEST_GARMENT.model_copy(update={"secondary_colors": ["grey", "white"], "brand": "engineered  garments"})
    results = tag_evals.compare(saved, tagged)
    assert results["secondary_colors"] == results["brand"] == tag_evals.MATCH


def test_materials_compare_by_fiber_and_percent_whatever_the_part():
    saved = TEST_GARMENT.model_copy(update={"materials": [MaterialPart(part="shell", fibers=[Fiber(fiber="Wool", percent=80), Fiber(fiber="nylon", percent=20)])]})
    same = TEST_GARMENT.model_copy(update={"materials": [MaterialPart(fibers=[Fiber(fiber="nylon", percent=20), Fiber(fiber="wool", percent=80)])]})
    other = TEST_GARMENT.model_copy(update={"materials": [MaterialPart(fibers=[Fiber(fiber="wool", percent=100)])]})
    assert tag_evals.compare(saved, same)["materials"] == tag_evals.MATCH
    assert tag_evals.compare(saved, other)["materials"] == tag_evals.DIFFER


def test_photo_roles_are_matched_by_index():
    result = TaggingResult(garment=TEST_GARMENT, photos=[PhotoTag(index=0, role="back"), PhotoTag(index=1, role="detail")])
    assert tag_evals.role_matches(["back", "label"], result) == 1


# --- a run ----------------------------------------------------------------------------------

def test_a_run_writes_results_and_scores(owner_db, garments_dir, tmp_path):
    garment_id = add(owner_db, garments_dir)
    out = run(owner_db, tmp_path, runs=2)
    rows = rows_of(out)
    assert [(r["garment_id"], r["run"]) for r in rows] == [(garment_id, 1), (garment_id, 2)]
    assert rows[0]["provider"] == "anthropic" and rows[0]["model"] == config.MODELS_BY_PROVIDER["anthropic"]["tag"]
    assert rows[0]["roles"]["saved"] == ["front", "label"]
    scores = (out / "scores.md").read_text(encoding="utf-8")
    assert "| primary_color | 2 | 2 | 100% |" in scores     # test mode tags TEST_GARMENT, which is what was saved
    assert f"### #{garment_id}" in scores


def test_a_run_changes_nothing_in_the_wardrobe(owner_db, garments_dir, tmp_path):
    add(owner_db, garments_dir)
    before = owner_db.read_bytes()
    run(owner_db, tmp_path)
    assert owner_db.read_bytes() == before


def test_one_failed_garment_is_recorded_and_the_run_goes_on(owner_db, garments_dir, tmp_path, monkeypatch):
    first, second = add(owner_db, garments_dir), add(owner_db, garments_dir)
    usage = TokenUsage(model="gpt-6.1-terra", input_tokens=1_000_000, output_tokens=0)
    def tag(user_id, paths, log_path, client, is_test, prompt, language, preferences):
        if len(calls) == 0:
            calls.append(1)
            raise ServiceError("Slow down.", "RateLimitError")
        return TaggingResult(garment=TEST_GARMENT, photos=[PhotoTag(index=0, role="front"), PhotoTag(index=1, role="label")]), usage
    calls = []
    monkeypatch.setattr(tag_evals, "tag_photos", tag)
    rows = rows_of(run(owner_db, tmp_path))
    assert rows[0]["garment_id"] == first and "RateLimitError" in rows[0]["error"]
    assert rows[1]["garment_id"] == second and rows[1]["roles"]["matched"] == 2
    assert tag_evals.total_cost(rows) == pytest.approx(config.MODEL_PRICES["gpt-6.1-terra"]["input"])


def test_an_unusable_answer_still_counts_its_tokens(owner_db, garments_dir, tmp_path, monkeypatch):
    add(owner_db, garments_dir)
    usage = TokenUsage(model="gpt-6.1-terra", input_tokens=1_000_000, output_tokens=0)
    def tag(*args):
        raise UnusableResponse("No garment in response (stop_reason=max_output_tokens)", usage)
    monkeypatch.setattr(tag_evals, "tag_photos", tag)
    [row] = rows_of(run(owner_db, tmp_path))
    assert "max_output_tokens" in row["error"]
    assert tag_evals.total_cost([row]) == pytest.approx(config.MODEL_PRICES["gpt-6.1-terra"]["input"])

def test_no_garments_with_photos_fails_before_any_call(owner_db, garments_dir, tmp_path):
    with pytest.raises(ValueError, match="no garments with photos"):
        run(owner_db, tmp_path)
    assert not (tmp_path / "evals").exists()


# --- the command ----------------------------------------------------------------------------

def run_main(monkeypatch, tmp_path, owner_db, *flags):
    monkeypatch.setattr(tag_evals, "load_dotenv", lambda: None)   # never the real .env
    monkeypatch.setattr(tag_evals, "TAG_EVALS_DIR", tmp_path / "evals")
    monkeypatch.setenv("ENCLOTHED_LLM_PROVIDER", "anthropic")      # so monkeypatch undoes what --provider sets
    monkeypatch.setattr(config, "OPENAI_IMAGE_DETAIL", config.OPENAI_IMAGE_DETAIL)   # likewise --image-detail
    monkeypatch.setattr("sys.argv", ["eval-tags", "-l", "cmp", "-t", "--db", str(owner_db), *flags])
    tag_evals.main()
    [out] = (tmp_path / "evals").iterdir()
    return rows_of(out)


def test_the_provider_and_detail_flags_apply_to_the_run(owner_db, garments_dir, tmp_path, monkeypatch):
    add(owner_db, garments_dir)
    [row] = run_main(monkeypatch, tmp_path, owner_db, "--provider", "openai", "--image-detail", "original")
    assert (row["provider"], row["image_detail"]) == ("openai", "original")
    assert config.OPENAI_IMAGE_DETAIL == "original"


def test_image_detail_is_refused_off_openai(owner_db, garments_dir, tmp_path, monkeypatch):
    add(owner_db, garments_dir)
    with pytest.raises(SystemExit):
        run_main(monkeypatch, tmp_path, owner_db, "--image-detail", "original")

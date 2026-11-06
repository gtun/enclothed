"""Mend: only blank fields, only valid values, and nothing private sent."""
import json
from datetime import date

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from enclothed import api, config, db, llm, main, mend, photos
from enclothed.auth import signed_in_user
from enclothed.db import init_db, insert_garment, select_garment
from enclothed.llm import UnusableResponse
from enclothed.models import Garment, MENDABLE_FIELDS, TokenUsage, User, blank_fields

USAGE = TokenUsage(model="claude-sonnet-5-5", input_tokens=1000, output_tokens=100)


def bare(**fields) -> Garment:
    values = {"category": "top", "subcategory": "t-shirt", "primary_color": "black", "styling_notes": "Plain.", **fields}
    return Garment(**values)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    monkeypatch.setattr(photos, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(photos, "THUMBS_DIR", tmp_path / "thumbs")
    return path


@pytest.fixture
def log_path(tmp_path):
    return tmp_path / "tagging_log.jsonl"


def add(db_path, tmp_path, garment=None, with_photo=True):
    garment_id = insert_garment(db_path, 1, garment or bare())
    if with_photo:
        folder = tmp_path / "garments" / str(garment_id)
        folder.mkdir(parents=True)
        Image.new("RGB", (40, 40), "navy").save(folder / "front_00.jpg")
    return garment_id


@pytest.fixture
def llm_answers(monkeypatch):
    """What the fake LLM answers, and what it was asked."""
    class Fake:
        answers = {"fit": "regular", "hem": "hip"}
        calls = []
    Fake.calls = []
    def fake(client, paths, record, blanks, language="en-US", preferences=None):
        Fake.calls.append({"paths": paths, "record": record, "blanks": blanks, "language": language, "preferences": preferences})
        return dict(Fake.answers), USAGE
    monkeypatch.setattr(mend, "fill_blanks", fake)
    return Fake


# --- which fields count as blank ------------------------------------------------------------

def test_empty_fields_that_apply_are_blank():
    assert {"fit", "shape", "hem", "sleeve", "fabric_type", "brand", "materials", "style_tags"} <= set(blank_fields(bare()))


def test_filled_fields_arent_blank():
    assert "fit" not in blank_fields(bare(fit="slim"))


def test_empty_secondary_colors_arent_blank():
    """Empty means the garment has none."""
    assert "secondary_colors" not in MENDABLE_FIELDS


@pytest.mark.parametrize("category, subcategory, missing", [
    ("bottom", "jeans", {"sleeve"}),
    ("shoes", "loafers", {"fit", "shape", "hem", "fabric_weight", "sleeve"}),
    ("accessory", "belt", {"fit", "shape", "hem", "fabric_weight", "sleeve"}),
])
def test_fields_that_dont_apply_are_never_blank(category, subcategory, missing):
    assert not missing & set(blank_fields(bare(category=category, subcategory=subcategory)))


def test_fabric_type_applies_to_shoes():
    assert "fabric_type" in blank_fields(bare(category="shoes", subcategory="loafers"))


# --- which answers are kept -----------------------------------------------------------------

def test_answers_to_filled_fields_are_dropped():
    assert mend.usable_answers(bare(fit="slim"), {"fit": "oversized", "hem": "hip"}) == {"hem": "hip"}


def test_answers_to_fields_that_dont_apply_are_dropped():
    assert mend.usable_answers(bare(category="shoes", subcategory="loafers"), {"hem": "ankle"}) == {}


def test_invalid_answers_are_dropped_and_the_rest_kept():
    assert mend.usable_answers(bare(), {"formality": 9, "hem": "hip"}) == {"hem": "hip"}


def test_empty_answers_are_dropped():
    assert mend.usable_answers(bare(), {"brand": "", "style_tags": [], "hem": None}) == {}


def test_a_fabric_off_the_list_becomes_other():
    assert mend.usable_answers(bare(), {"fabric_type": "moon cloth"}) == {"fabric_type": "other"}


# --- mend_garment ---------------------------------------------------------------------------

def test_the_llm_gets_only_the_blank_fields_and_no_private_notes(db_path, log_path, tmp_path, llm_answers):
    garment_id = add(db_path, tmp_path, bare(fit="slim", notes="paid too much"))
    garment = select_garment(db_path, 1, garment_id)

    mend.mend_garment(db_path, log_path, 1, garment, None)

    [call] = llm_answers.calls
    assert call["blanks"] == blank_fields(garment)
    assert "fit" not in call["blanks"]
    assert call["record"]["fit"] == "slim"
    assert "notes" not in call["record"]
    assert "paid too much" not in json.dumps(call["record"])


def test_mend_saves_no_answers_but_records_the_attempt(db_path, log_path, tmp_path, llm_answers):
    garment_id = add(db_path, tmp_path)
    result = mend.mend_garment(db_path, log_path, 1, select_garment(db_path, 1, garment_id), None)

    saved = select_garment(db_path, 1, garment_id)
    assert result.filled == {"fit": "regular", "hem": "hip"}
    assert "brand" in result.unanswered
    assert saved.fit is None
    assert saved.mended_on == date.today()


def test_mend_shows_up_as_tagging_spend(db_path, log_path, tmp_path, llm_answers):
    garment_id = add(db_path, tmp_path)
    mend.mend_garment(db_path, log_path, 1, select_garment(db_path, 1, garment_id), None)

    entry = json.loads(log_path.read_text())
    assert entry["mend"] is True
    assert entry["usage"]["input_tokens"] == 1000


def test_no_photos_means_no_llm_call(db_path, log_path, tmp_path, llm_answers):
    garment_id = add(db_path, tmp_path, with_photo=False)
    with pytest.raises(mend.NoPhotos):
        mend.mend_garment(db_path, log_path, 1, select_garment(db_path, 1, garment_id), None)
    assert llm_answers.calls == []


def test_a_response_with_no_fields_still_logs_its_cost(db_path, log_path, tmp_path, monkeypatch):
    def fake(*args, **kwargs):
        raise UnusableResponse("empty", USAGE)
    monkeypatch.setattr(mend, "fill_blanks", fake)
    garment_id = add(db_path, tmp_path)

    with pytest.raises(UnusableResponse):
        mend.mend_garment(db_path, log_path, 1, select_garment(db_path, 1, garment_id), None)
    assert json.loads(log_path.read_text())["usage"]["input_tokens"] == 1000


def test_big_or_unusual_photos_are_shrunk_before_sending(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MEND_MAX_PHOTO_BYTES", 10)
    big = tmp_path / "front_00.jpg"
    Image.new("RGB", (100, 100), "red").save(big)
    out = tmp_path / "out"
    out.mkdir()

    [ready] = mend._sendable([big], out)

    assert ready.parent == out
    assert ready.suffix == ".jpg"


def test_small_photos_are_sent_as_they_are(tmp_path):
    small = tmp_path / "front_00.jpg"
    Image.new("RGB", (10, 10), "red").save(small)
    assert mend._sendable([small], tmp_path) == [small]


# --- what the LLM is told -------------------------------------------------------------------

class FakeParse:
    def __init__(self, parsed=True):
        self.sent = None
        self.parsed = parsed

    def __call__(self, **kwargs):
        self.sent = kwargs
        usage = type("Usage", (), {"input_tokens": 1, "output_tokens": 1})()
        parsed = kwargs["output_format"](hem="hip") if self.parsed else None
        return type("Response", (), {"usage": usage, "parsed_output": parsed, "stop_reason": "end_turn"})()


def fake_client(parse):
    return type("Client", (), {"messages": type("Messages", (), {"parse": parse})()})()


def test_the_output_schema_has_only_the_blank_fields(tmp_path):
    photo = tmp_path / "front.jpg"
    photo.write_bytes(b"jpeg")
    parse = FakeParse()

    answers, _ = llm.fill_blanks(fake_client(parse), [photo], {"category": "top"}, ["hem", "fit"], preferences="I'm tall")

    assert set(parse.sent["output_format"].model_fields) == {"hem", "fit"}
    assert answers == {"hem": "hip"}
    text = " ".join(block["text"] for block in parse.sent["messages"][0]["content"] if block["type"] == "text")
    assert "Fill in only these blank fields: hem, fit" in text
    assert "I'm tall" in text
    assert "Filling in blanks" in parse.sent["system"]


def test_no_parsed_output_is_unusable(tmp_path):
    photo = tmp_path / "front.jpg"
    photo.write_bytes(b"jpeg")
    with pytest.raises(UnusableResponse):
        llm.fill_blanks(fake_client(FakeParse(parsed=False)), [photo], {}, ["hem"])


# --- the bulk run ---------------------------------------------------------------------------

def test_a_bulk_run_saves_answers_and_keeps_existing_values(db_path, log_path, tmp_path, llm_answers, capsys):
    garment_id = add(db_path, tmp_path, bare(brand="Levi's", notes="mine"))

    assert mend.mend_all(db_path, log_path, 1, None) == 0

    saved = select_garment(db_path, 1, garment_id)
    assert (saved.fit, saved.hem, saved.brand, saved.notes) == ("regular", "hip", "Levi's", "mine")
    assert saved.mended_on == date.today()
    assert "fit=regular" in capsys.readouterr().out


def test_a_second_run_skips_garments_already_tried(db_path, log_path, tmp_path, llm_answers):
    add(db_path, tmp_path)
    mend.mend_all(db_path, log_path, 1, None)
    mend.mend_all(db_path, log_path, 1, None)
    assert len(llm_answers.calls) == 1


def test_retry_includes_garments_already_tried(db_path, log_path, tmp_path, llm_answers):
    add(db_path, tmp_path)
    mend.mend_all(db_path, log_path, 1, None)
    mend.mend_all(db_path, log_path, 1, None, retry=True)
    assert len(llm_answers.calls) == 2


def test_limit_stops_early_and_the_next_run_picks_up_the_rest(db_path, log_path, tmp_path, llm_answers):
    for _ in range(3):
        add(db_path, tmp_path)
    mend.mend_all(db_path, log_path, 1, None, limit=2)
    assert len(llm_answers.calls) == 2
    mend.mend_all(db_path, log_path, 1, None)
    assert len(llm_answers.calls) == 3


def test_named_ids_are_the_only_ones_mended(db_path, log_path, tmp_path, llm_answers):
    first = add(db_path, tmp_path)
    add(db_path, tmp_path)
    mend.mend_all(db_path, log_path, 1, None, ids=[first])
    assert len(llm_answers.calls) == 1


def test_disowned_garments_are_left_alone(db_path, log_path, tmp_path, llm_answers):
    add(db_path, tmp_path, bare(disowned_on=date(2026, 1, 1)))
    mend.mend_all(db_path, log_path, 1, None)
    assert llm_answers.calls == []


def test_a_garment_with_no_photos_is_skipped_and_can_be_tried_later(db_path, log_path, tmp_path, llm_answers, capsys):
    garment_id = add(db_path, tmp_path, with_photo=False)
    assert mend.mend_all(db_path, log_path, 1, None) == 0
    assert "skipped" in capsys.readouterr().out
    assert select_garment(db_path, 1, garment_id).mended_on is None


def api_error():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://example.com"))


def test_one_failure_doesnt_stop_the_run(db_path, log_path, tmp_path, monkeypatch):
    calls = []
    def flaky(client, paths, record, blanks, language="en-US", preferences=None):
        calls.append(1)
        if len(calls) == 1:
            raise api_error()
        return {"hem": "hip"}, USAGE
    monkeypatch.setattr(mend, "fill_blanks", flaky)
    add(db_path, tmp_path)
    add(db_path, tmp_path)

    assert mend.mend_all(db_path, log_path, 1, None) == 1
    assert len(calls) == 2


def test_repeated_failures_stop_the_run(db_path, log_path, tmp_path, monkeypatch):
    calls = []
    def broken(*args, **kwargs):
        calls.append(1)
        raise api_error()
    monkeypatch.setattr(mend, "fill_blanks", broken)
    for _ in range(5):
        add(db_path, tmp_path)

    mend.mend_all(db_path, log_path, 1, None)

    assert len(calls) == mend.MAX_FAILURES_IN_A_ROW


def test_a_failed_garment_is_tried_again_next_run(db_path, log_path, tmp_path, monkeypatch, llm_answers):
    garment_id = add(db_path, tmp_path)
    def broken(*args, **kwargs):
        raise api_error()
    monkeypatch.setattr(mend, "fill_blanks", broken)
    mend.mend_all(db_path, log_path, 1, None)
    assert select_garment(db_path, 1, garment_id).mended_on is None


# --- POST /api/garments/{id}/mend -----------------------------------------------------------

@pytest.fixture
def client(db_path, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DB_PATH", db_path)
    monkeypatch.setattr(api, "TAGGING_LOG_PATH", tmp_path / "tagging_log.jsonl")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    api.app.dependency_overrides[signed_in_user] = lambda: User(id=1, username="owner", is_admin=True)
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def test_the_route_proposes_and_saves_nothing(client, db_path, tmp_path, llm_answers):
    garment_id = add(db_path, tmp_path)
    response = client.post(f"/api/garments/{garment_id}/mend")

    assert response.status_code == 200
    assert response.json()["filled"] == {"fit": "regular", "hem": "hip"}
    assert "brand" in response.json()["unanswered"]
    assert client.get(f"/api/garments/{garment_id}").json()["fit"] is None


def test_garments_list_their_blank_fields(client, db_path, tmp_path):
    garment_id = add(db_path, tmp_path, bare(fit="slim"))
    blanks = client.get(f"/api/garments/{garment_id}").json()["blank_fields"]
    assert "hem" in blanks
    assert "fit" not in blanks


def test_the_route_passes_saved_preferences(client, db_path, tmp_path, llm_answers):
    db.save_preferences(db_path, 1, "I'm 5 foot 4", "2026-11-06T00:00:00+00:00")
    client.post(f"/api/garments/{add(db_path, tmp_path)}/mend")
    assert llm_answers.calls[0]["preferences"] == "I'm 5 foot 4"


def test_mending_a_complete_garment_is_refused(client, db_path, tmp_path, llm_answers, monkeypatch):
    monkeypatch.setattr(api, "blank_fields", lambda garment: [])
    assert client.post(f"/api/garments/{add(db_path, tmp_path)}/mend").status_code == 422
    assert llm_answers.calls == []


def test_mending_with_no_photos_is_refused(client, db_path, tmp_path, llm_answers):
    assert client.post(f"/api/garments/{add(db_path, tmp_path, with_photo=False)}/mend").status_code == 422


def test_an_unknown_garment_is_404(client):
    assert client.post("/api/garments/999/mend").status_code == 404


def test_mended_on_cant_be_edited(client, db_path, tmp_path):
    assert client.patch(f"/api/garments/{add(db_path, tmp_path)}", json={"mended_on": "2026-01-01"}).status_code == 422


# --- the command ----------------------------------------------------------------------------

def test_the_command_runs_on_the_chosen_wardrobe(db_path, tmp_path, llm_answers, monkeypatch, capsys):
    garment_id = add(db_path, tmp_path)
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "TAGGING_LOG_PATH", tmp_path / "tagging_log.jsonl")
    monkeypatch.setattr(config, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(config, "INTAKE_DIR", tmp_path / "intake")
    monkeypatch.setattr(main, "Anthropic", lambda: None)
    monkeypatch.setattr("sys.argv", ["enclothed", "mend", "--limit", "1"])

    assert main.main() == 0
    assert select_garment(db_path, 1, garment_id).hem == "hip"

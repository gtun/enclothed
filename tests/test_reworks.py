# Rework: which photo is sent, what's saved and logged, deleting, and cleaning up after deleted garments.
# preview_garment is always a fake; nothing here makes an API call.
import io
import json
from datetime import date

import pytest
from PIL import Image

from enclothed import config, db, photos, reworks
from enclothed.intake import TEST_GARMENT
from enclothed.llm import Client, UnusableResponse
from enclothed.models import ImageUsage

USAGE = ImageUsage(model="gpt-image-2.5-sunburst", text_input_tokens=87, image_input_tokens=1452, output_tokens=386)
CLIENT = Client("openai", None)


def png(color="blue"):
    out = io.BytesIO()
    Image.new("RGB", (30, 40), color).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "enclothed.db"
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    return path


@pytest.fixture
def garment_id(db_path, tmp_path):
    garment_id = db.insert_garment(db_path, 1, TEST_GARMENT)
    folder = tmp_path / "garments" / str(garment_id)
    folder.mkdir(parents=True)
    for role, color in [("back", "gray"), ("front", "navy"), ("label", "white")]:
        Image.new("RGB", (20, 20), color).save(folder / f"{role}_00.jpg")
    return garment_id


def run(db_path, tmp_path, garment_id, instruction="Make it bright blue"):
    return reworks.rework_garment(db_path, tmp_path / "reworks", tmp_path / "rework_log.jsonl", 1, garment_id, instruction, CLIENT)


def log_lines(tmp_path):
    return [json.loads(line) for line in (tmp_path / "rework_log.jsonl").read_text(encoding="utf-8").splitlines()]


# --- which photo ------------------------------------------------------------------------------

def test_the_front_photo_is_sent(tmp_path):
    paths = [tmp_path / "back_00.jpg", tmp_path / "front_00.jpg", tmp_path / "label_00.jpg"]
    assert reworks.source_photo(paths) == paths[1]


def test_without_a_front_photo_the_first_is_sent(tmp_path):
    paths = [tmp_path / "detail_00.jpg", tmp_path / "label_00.jpg"]
    assert reworks.source_photo(paths) == paths[0]


# --- making one -------------------------------------------------------------------------------

def test_a_rework_is_saved_as_a_jpeg_with_its_row_and_log_line(db_path, tmp_path, garment_id, monkeypatch):
    sent = []

    def fake_preview(client, photo, instruction):
        with Image.open(photo) as image:
            red, _, blue = image.getpixel((0, 0))
            sent.append(("navy" if blue > 100 > red else "not navy", instruction))
        return png(), USAGE

    monkeypatch.setattr(reworks, "preview_garment", fake_preview)
    rework = run(db_path, tmp_path, garment_id)
    assert sent == [("navy", "Make it bright blue")]   # the front photo
    assert {k: rework[k] for k in ("garment_id", "instruction", "source_photo", "model")} == {
        "garment_id": garment_id, "instruction": "Make it bright blue", "source_photo": "front_00.jpg", "model": USAGE.model}
    with Image.open(reworks.image_path(tmp_path / "reworks", rework["id"])) as saved:
        assert saved.format == "JPEG"
    [line] = log_lines(tmp_path)
    assert (line["user_id"], line["garment_id"], line["rework_id"], line["image_usage"]) == (1, garment_id, rework["id"], USAGE.model_dump())
    assert "Make it bright blue" not in json.dumps(line)   # the person's words stay in the database only


def test_the_rework_is_kept_apart_from_the_garments_photos(db_path, tmp_path, garment_id, monkeypatch):
    monkeypatch.setattr(reworks, "preview_garment", lambda client, photo, instruction: (png(), USAGE))
    run(db_path, tmp_path, garment_id)
    assert sorted(p.name for p in photos.get_photo_paths(garment_id)) == ["back_00.jpg", "front_00.jpg", "label_00.jpg"]


def test_a_garment_without_photos_is_refused_before_any_call(db_path, tmp_path, monkeypatch):
    monkeypatch.setattr(reworks, "preview_garment", lambda *args: pytest.fail("no call without a photo"))
    garment_id = db.insert_garment(db_path, 1, TEST_GARMENT)
    with pytest.raises(reworks.NoPhotos):
        run(db_path, tmp_path, garment_id)


def test_an_answer_with_no_image_saves_nothing_but_logs_its_tokens(db_path, tmp_path, garment_id, monkeypatch):
    def no_image(client, photo, instruction):
        raise UnusableResponse("No image in the response", USAGE)

    monkeypatch.setattr(reworks, "preview_garment", no_image)
    with pytest.raises(UnusableResponse):
        run(db_path, tmp_path, garment_id)
    assert db.select_garment_reworks(db_path, 1, garment_id) == []
    [line] = log_lines(tmp_path)
    assert line["image_usage"] == USAGE.model_dump() and line["rework_id"] is None and "No image" in line["error"]


def test_an_image_that_cant_be_read_leaves_no_row(db_path, tmp_path, garment_id, monkeypatch):
    monkeypatch.setattr(reworks, "preview_garment", lambda client, photo, instruction: (b"not an image", USAGE))
    with pytest.raises(Exception):
        run(db_path, tmp_path, garment_id)
    assert db.select_garment_reworks(db_path, 1, garment_id) == []


# --- listing, deleting, cleaning up -----------------------------------------------------------

def test_reworks_list_newest_first_and_only_the_owners(db_path, tmp_path, garment_id, monkeypatch):
    monkeypatch.setattr(reworks, "preview_garment", lambda client, photo, instruction: (png(), USAGE))
    first, second = run(db_path, tmp_path, garment_id, "blue"), run(db_path, tmp_path, garment_id, "red")
    assert [r["id"] for r in db.select_garment_reworks(db_path, 1, garment_id)] == [second["id"], first["id"]]
    assert db.select_garment_reworks(db_path, 2, garment_id) == []
    assert db.select_rework(db_path, 2, first["id"]) is None


def test_deleting_removes_the_row_and_the_image(db_path, tmp_path, garment_id, monkeypatch):
    monkeypatch.setattr(reworks, "preview_garment", lambda client, photo, instruction: (png(), USAGE))
    rework = run(db_path, tmp_path, garment_id)
    assert not reworks.delete(db_path, tmp_path / "reworks", 2, rework["id"])   # someone else's
    assert reworks.delete(db_path, tmp_path / "reworks", 1, rework["id"])
    assert db.select_rework(db_path, 1, rework["id"]) is None
    assert not reworks.image_path(tmp_path / "reworks", rework["id"]).exists()
    assert not reworks.delete(db_path, tmp_path / "reworks", 1, rework["id"])


def test_deleting_a_garment_deletes_its_reworks_and_the_next_start_removes_the_images(db_path, tmp_path, monkeypatch):
    monkeypatch.setattr(reworks, "preview_garment", lambda client, photo, instruction: (png(), USAGE))
    candidate = db.insert_garment(db_path, 1, TEST_GARMENT.model_copy(update={"weighed_on": date(2026, 11, 20)}))
    folder = tmp_path / "garments" / str(candidate)
    folder.mkdir(parents=True)
    Image.new("RGB", (20, 20)).save(folder / "front_00.jpg")
    rework = run(db_path, tmp_path, candidate)
    assert db.delete_candidate(db_path, 1, candidate)
    assert db.select_rework_ids(db_path) == set()
    stray = tmp_path / "reworks" / "notes.jpg"
    stray.write_bytes(b"x")
    reworks.remove_orphaned_files(db_path, tmp_path / "reworks")
    assert list((tmp_path / "reworks").iterdir()) == []
    assert not reworks.image_path(tmp_path / "reworks", rework["id"]).exists()


def test_cleaning_up_with_no_folder_yet_is_fine(db_path, tmp_path):
    reworks.remove_orphaned_files(db_path, tmp_path / "reworks")

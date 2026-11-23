# eval-previews: which photo is sent, the files a run writes, and failed calls. Runs use test mode (grey
# placeholders, no client) or a fake preview_garment; none make an API call.
import json

import pytest
from PIL import Image

from enclothed import config, db, photos, preview_evals
from enclothed.intake import TEST_GARMENT
from enclothed.llm import ServiceError, UnusableResponse
from enclothed.models import ImageUsage


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


def add(db_path, garments_dir, roles=("label", "front")):
    garment_id = db.insert_garment(db_path, 1, TEST_GARMENT.model_copy())
    folder = garments_dir / str(garment_id)
    folder.mkdir(parents=True)
    for role in roles:
        Image.new("RGB", (20, 20), "navy" if role == "front" else "white").save(folder / f"{role}_00.jpg")
    return garment_id


def rows_of(out):
    return [json.loads(line) for line in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]


def run(owner_db, tmp_path, ids=None, runs=1, is_test=True):
    return preview_evals.run("blue", "Make it <bright> blue", runs, 1, owner_db, ids, 3, is_test, tmp_path / "evals", "low")


def test_the_front_photo_is_sent(tmp_path):
    paths = [tmp_path / "back_00.jpg", tmp_path / "front_00.jpg", tmp_path / "label_00.jpg"]
    assert preview_evals.photo_to_send(paths) == paths[1]


def test_without_a_front_photo_the_first_is_sent(tmp_path):
    paths = [tmp_path / "detail_00.jpg", tmp_path / "label_00.jpg"]
    assert preview_evals.photo_to_send(paths) == paths[0]


def test_a_test_run_writes_the_photo_a_grey_preview_and_a_page(owner_db, garments_dir, tmp_path):
    garment_id = add(owner_db, garments_dir)
    out = run(owner_db, tmp_path, runs=2)
    rows = rows_of(out)
    assert [(r["garment_id"], r["run"], r["error"]) for r in rows] == [(garment_id, 1, None), (garment_id, 2, None)]
    with Image.open(out / rows[0]["photo"]) as sent:
        assert sent.getpixel((0, 0))[2] > 100   # the navy front photo, not the white label
    with Image.open(out / rows[0]["preview"]) as preview:
        assert preview.mode == "L"
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "Make it &lt;bright&gt; blue" in page
    assert f'src="{rows[1]["preview"]}"' in page


def test_previews_are_saved_and_priced(owner_db, garments_dir, tmp_path, monkeypatch):
    add(owner_db, garments_dir)
    monkeypatch.setattr(preview_evals, "make_client", lambda provider: object())
    usage = ImageUsage(model="gpt-image-2.5-sunburst", text_input_tokens=100, image_input_tokens=1000, output_tokens=1000)
    calls = []

    def fake_preview(client, photo, instruction, quality):
        calls.append((photo.name, instruction, quality))
        return b"png bytes", usage

    monkeypatch.setattr(preview_evals, "preview_garment", fake_preview)
    out = run(owner_db, tmp_path, is_test=False)
    row = rows_of(out)[0]
    assert calls == [(row["photo"], "Make it <bright> blue", "low")]
    assert (out / row["preview"]).read_bytes() == b"png bytes"
    assert preview_evals.total_cost([row]) == pytest.approx((100 * 5 + 1000 * 8 + 1000 * 30) / 1_000_000)


def test_one_failed_preview_does_not_stop_the_run(owner_db, garments_dir, tmp_path, monkeypatch):
    first, second = add(owner_db, garments_dir), add(owner_db, garments_dir)
    monkeypatch.setattr(preview_evals, "make_client", lambda provider: object())
    usage = ImageUsage(model="gpt-image-2.5-sunburst", text_input_tokens=1, image_input_tokens=1, output_tokens=1)

    def fake_preview(client, photo, instruction, quality):
        if photo.name.startswith(f"{first}_"):
            raise ServiceError("Your request was rejected by the safety system", "BadRequestError")
        raise UnusableResponse("No image in the response", usage)

    monkeypatch.setattr(preview_evals, "preview_garment", fake_preview)
    out = run(owner_db, tmp_path, ids=[first, second], is_test=False)
    rows = rows_of(out)
    assert [r["error"].split(":")[0] for r in rows] == ["BadRequestError", "UnusableResponse"]
    assert rows[0]["usage"] is None and rows[1]["usage"]["output_tokens"] == 1
    assert "failed: BadRequestError" in (out / "index.html").read_text(encoding="utf-8")


def test_an_unknown_garment_stops_the_run_before_any_call(owner_db, garments_dir, tmp_path):
    garment_id = add(owner_db, garments_dir)
    with pytest.raises(ValueError, match=str(garment_id + 1)):
        run(owner_db, tmp_path, ids=[garment_id + 1])
    assert not (tmp_path / "evals").exists()

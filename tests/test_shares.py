# tests/test_shares.py: share links, a frozen anonymous copy of a garment or an outfit for anyone with the link
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from enclothed import api, photos, shares
from enclothed.auth import signed_in_user
from enclothed.config import MIGRATIONS_DIR, PUBLIC_DIR, SCHEMA_PATH
from enclothed.db import init_db, insert_garment, insert_outfits, insert_set, insert_user, insert_wear, select_garment, update_garment
from enclothed.intake import TEST_GARMENT
from enclothed.models import Outfit, User

OWNER = User(id=1, username="gtun-the-owner", is_admin=True, language="zh-TW")
GARMENT_KEYS = {"category", "subcategory", "brand", "primary_color", "secondary_colors", "accent_colors",
                "fabric_type", "materials", "country_of_origin", "style_tags", "photos"}


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(photos, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(photos, "THUMBS_DIR", tmp_path / "thumbs")
    return path


class Owner:
    """Signed in as the owner for each of its own requests only, so a stranger's requests never are."""
    def __init__(self):
        self.client = TestClient(api.app)

    def post(self, *args, **kwargs):
        api.app.dependency_overrides[signed_in_user] = lambda: OWNER
        try:
            return self.client.post(*args, **kwargs)
        finally:
            api.app.dependency_overrides.clear()


@pytest.fixture
def owner(db_path):
    return Owner()


@pytest.fixture
def stranger(db_path, monkeypatch):
    """Someone with the link and no account: no sign-in of any kind is set up."""
    for name in ("ENCLOTHED_DEV_USER", "ACCESS_TEAM_NAME", "AUD_TAG"):
        monkeypatch.delenv(name, raising=False)
    return TestClient(api.app)


def add_photo(garment_id, name="front_00.jpg", gps=False):
    folder = photos.GARMENTS_DIR / str(garment_id)
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (2400, 3200), "navy")
    exif = Image.Exif()
    if gps:
        exif[0x010F] = "PhoneMaker"                     # camera make
        exif[0x8825] = {1: "N", 2: (40.0, 43.0, 0.0)}   # GPS: where the photo was taken
    image.save(folder / name, "JPEG", exif=exif.tobytes())
    return folder / name


@pytest.fixture
def garment_id(db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT.model_copy(update={"brand": "Kapital", "fabric_type": "corduroy"}))
    add_photo(garment_id, "front_00.jpg", gps=True)
    add_photo(garment_id, "label_01.jpg")
    return garment_id


@pytest.fixture
def outfit_id(db_path, garment_id):
    other = insert_garment(db_path, 1, TEST_GARMENT.model_copy(update={"category": "bottom", "subcategory": "jeans", "primary_color": "indigo"}))
    insert_set(db_path, 1, [other], "My gtun suit")
    outfit = Outfit(aesthetic="Workwear Americana", explanation="Corduroy over denim.", missing="A belt.", risk_tier="stretch",
                    garments=[{"garment_id": garment_id, "styling_advice": "Leave it open"}, {"garment_id": other}])
    [new_id] = insert_outfits(db_path, 1, [outfit], [garment_id], "dinner at Kwan's parents", "2026-11-01T00:00:00+00:00")
    insert_wear(db_path, 1, new_id, datetime(2026, 11, 2).date(), "with gtun")
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("UPDATE outfits SET liked = 1 WHERE id = ?", (new_id,))
    return new_id


def make(client, kind, item_id):
    response = client.post("/api/shares", json={"kind": kind, "id": item_id})
    assert response.status_code == 201, response.text
    body = response.json()
    assert re.fullmatch(r"/s/[A-Za-z0-9_-]{20,}", body["path"])
    return body


def all_text(value) -> str:
    return repr(value)


# --- what a share holds ----------------------------------------------------------------
def test_a_garment_share_holds_only_the_listed_details_and_its_photos(owner, stranger, garment_id):
    data = stranger.get(make(owner, "garment", garment_id)["path"] + "/data").json()

    assert data["kind"] == "garment" and data["language"] == "zh-TW"
    assert set(data["garment"]) == GARMENT_KEYS
    assert data["garment"]["brand"] == "Kapital" and data["garment"]["fabric_type"] == "corduroy"
    assert data["garment"]["photos"] == [{"role": "front", "file": "front_00.jpg"}, {"role": "label", "file": "label_01.jpg"}]
    for private in ("notes", "styling_notes", "formality", "id", "user_id", "set_id", "gtun", "2nd Street"):
        assert private not in all_text(data)


def test_an_outfit_share_leaves_out_the_request_rating_wears_ids_and_names(owner, stranger, outfit_id, garment_id):
    data = stranger.get(make(owner, "outfit", outfit_id)["path"] + "/data").json()

    outfit = data["outfit"]
    assert set(outfit) == {"aesthetic", "explanation", "missing", "risk_tier", "timestamp", "pieces"}
    assert (outfit["aesthetic"], outfit["missing"], outfit["risk_tier"]) == ("Workwear Americana", "A belt.", "stretch")
    assert outfit["pieces"][0] == {"garment": 0, "styling_advice": "Leave it open", "in_set": False, "set_name": None}
    assert outfit["pieces"][1]["in_set"] is True
    assert [set(g) for g in data["garments"]] == [GARMENT_KEYS, GARMENT_KEYS]
    text = all_text({**data, "outfit": {**outfit, "pieces": [{**p, "set_name": None} for p in outfit["pieces"]]}})
    for private in ("dinner", "Kwan", "liked", "wears", "wear_count", "last_worn", "anchor", "prompt", "gtun", "look", "user_id", f"'id': {garment_id}"):
        assert private not in text


def test_a_share_is_a_copy_so_later_edits_never_reach_it(owner, stranger, db_path, garment_id):
    path = make(owner, "garment", garment_id)["path"]
    garment = select_garment(db_path, 1, garment_id)
    update_garment(db_path, 1, garment.model_copy(update={"brand": "Changed", "disowned_on": datetime(2026, 11, 3).date()}))
    for photo in (photos.GARMENTS_DIR / str(garment_id)).iterdir():
        photo.unlink()

    data = stranger.get(path + "/data").json()

    assert data["garment"]["brand"] == "Kapital"
    assert stranger.get(f"{path}/photos/0/front_00.jpg").status_code == 200


def test_shared_photos_carry_no_camera_details_or_location(owner, stranger, garment_id):
    path = make(owner, "garment", garment_id)["path"]
    response = stranger.get(f"{path}/photos/0/front_00.jpg")
    thumb = stranger.get(f"{path}/thumbs/0/front_00.jpg")

    import io
    with Image.open(io.BytesIO(response.content)) as image:
        assert not image.getexif()
        assert max(image.size) == 1600
    with Image.open(io.BytesIO(thumb.content)) as image:
        assert max(image.size) <= 800
    assert response.headers["cache-control"].startswith("private")


def test_you_can_only_share_your_own_garments_and_outfits(owner, db_path, outfit_id):
    someone = insert_user(db_path, "someone", "someone@example.com")
    theirs = insert_garment(db_path, someone, TEST_GARMENT)
    assert owner.post("/api/shares", json={"kind": "garment", "id": theirs}).status_code == 404
    assert owner.post("/api/shares", json={"kind": "outfit", "id": outfit_id + 99}).status_code == 404


def test_making_a_share_needs_a_sign_in(stranger, garment_id):
    assert stranger.post("/api/shares", json={"kind": "garment", "id": garment_id}).status_code in (401, 503)


# --- the public pages ------------------------------------------------------------------
def test_anyone_with_the_link_can_open_the_page_without_signing_in(owner, stranger, outfit_id):
    path = make(owner, "outfit", outfit_id)["path"]

    page = stranger.get(path)
    assert page.status_code == 200 and "share.js" in page.text
    assert page.headers["x-robots-tag"].startswith("noindex") and page.headers["referrer-policy"] == "no-referrer"
    assert stranger.get(f"{path}/data").status_code == 200
    assert stranger.get(f"{path}/thumbs/0/front_00.jpg").status_code == 200
    assert stranger.get("/s/options/ja-JP").json()["category_labels"]["top"]
    assert stranger.get("/s/static/js/share.js").status_code == 200


def test_an_expired_or_unknown_link_shows_nothing(owner, stranger, db_path, garment_id):
    path = make(owner, "garment", garment_id)["path"]
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("UPDATE shares SET expires_at = '2026-01-01T00:00:00+00:00'")

    assert stranger.get(path).status_code == 404   # still the page, which says the link has expired
    assert stranger.get(f"{path}/data").status_code == 404
    assert stranger.get(f"{path}/photos/0/front_00.jpg").status_code == 404
    assert stranger.get("/s/not-a-real-token/data").status_code == 404


def test_a_photo_name_cant_reach_outside_its_share(owner, stranger, garment_id):
    path = make(owner, "garment", garment_id)["path"]
    assert stranger.get(f"{path}/photos/0/..%2F..%2Fenclothed.db").status_code == 404
    assert stranger.get(f"{path}/photos/0/.hidden").status_code == 404


def test_a_share_lasts_three_days(db_path, garment_id, tmp_path):
    now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
    token, expires_at = shares.share_garment(db_path, tmp_path / "shares", 1, garment_id, "en-US", now)

    assert expires_at == "2026-11-19T12:00:00+00:00"
    assert shares.load(db_path, token, now + timedelta(days=3, seconds=-1)) is not None
    assert shares.load(db_path, token, now + timedelta(days=3)) is None


def test_expired_shares_and_their_photos_are_deleted(db_path, garment_id, tmp_path):
    folder = tmp_path / "shares"
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    old, _ = shares.share_garment(db_path, folder, 1, garment_id, "en-US", now)
    new, _ = shares.share_garment(db_path, folder, 1, garment_id, "en-US", now + timedelta(days=2))
    assert (folder / old).is_dir()

    shares.purge_expired(db_path, folder, now + timedelta(days=4))

    assert not (folder / old).exists() and (folder / new).is_dir()
    assert shares.load(db_path, new, now + timedelta(days=4)) is not None


def test_a_photo_folder_with_no_share_is_removed_at_start_up(db_path, garment_id, tmp_path):
    folder = tmp_path / "shares"
    token, _ = shares.share_garment(db_path, folder, 1, garment_id, "en-US", datetime.now(timezone.utc))
    (folder / "left-behind" / "0").mkdir(parents=True)

    shares.remove_orphaned_photos(db_path, folder)

    assert sorted(p.name for p in folder.iterdir()) == [token]


def test_a_failed_share_leaves_no_photos_behind(db_path, garment_id, tmp_path, monkeypatch):
    def broken(*args):
        raise sqlite3.OperationalError("disk full")
    monkeypatch.setattr(shares.db, "insert_share", broken)

    with pytest.raises(sqlite3.OperationalError):
        shares.share_garment(db_path, tmp_path / "shares", 1, garment_id, "en-US", datetime.now(timezone.utc))
    assert list((tmp_path / "shares").iterdir()) == []


# --- the shared page's own files ---------------------------------------------------------
def share_page_scripts():
    html = (PUBLIC_DIR / "share.html").read_text()
    return html, re.findall(r'<script src="([^"]+)"', html)


def test_the_shared_page_loads_everything_from_the_open_path():
    html, scripts = share_page_scripts()
    assert all(src.startswith("/s/static/") for src in scripts)
    assert all(href.startswith(("/s/static/", "https://fonts.")) for href in re.findall(r'href="([^"]+)"', html) if href != "#")


def test_the_shared_page_has_no_wardrobe_account_ai_or_help_controls():
    html, scripts = share_page_scripts()
    for control in ("nav-wardrobe", "nav-outfits", "nav-style", "nav-usage", 'id="who"', "help-btn", "actbar", "insights", "builder"):
        assert control not in html
    for src in scripts:
        code = (PUBLIC_DIR / src.removeprefix("/s/static/")).read_text()
        assert not re.search(r"[\"'`]/api/", code), f"{src} calls the signed-in API"

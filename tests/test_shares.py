# tests/test_shares.py: share links, a frozen anonymous copy of a garment or an outfit for anyone with the link
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from enclothed import api, config, shares
from enclothed.auth import signed_in_user
from enclothed.config import MIGRATIONS_DIR, PUBLIC_DIR, SCHEMA_PATH
from enclothed.config import DEMO_SHARE_LIMIT
from enclothed.db import init_db, insert_demo_user, insert_garment, insert_outfits, insert_set, insert_share, insert_user, insert_wear, select_garment, update_garment
from enclothed.intake import TEST_GARMENT
from enclothed.models import Outfit, User

OWNER = User(id=1, username="gtun-the-owner", is_admin=True, language="zh-TW")
GARMENT_KEYS = {"category", "subcategory", "brand", "primary_color", "secondary_colors", "accent_colors",
                "fabric_type", "materials", "country_of_origin", "style_tags", "photos"}


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "DB_PATH", path)          # auth.current_user reads it, for acting as someone
    return path


class Owner:
    """Signed in as the owner (or another user) for each of its own requests only, so a stranger's requests never are."""
    def __init__(self, user=OWNER):
        self.client = TestClient(api.app)
        self.user = user

    def _send(self, method, *args, **kwargs):
        api.app.dependency_overrides[signed_in_user] = lambda: self.user
        try:
            return getattr(self.client, method)(*args, **kwargs)
        finally:
            api.app.dependency_overrides.clear()

    def post(self, *args, **kwargs):
        return self._send("post", *args, **kwargs)

    def get(self, *args, **kwargs):
        return self._send("get", *args, **kwargs)

    def put(self, *args, **kwargs):
        return self._send("put", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._send("delete", *args, **kwargs)


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
    folder = config.GARMENTS_DIR / str(garment_id)
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
    for photo in (config.GARMENTS_DIR / str(garment_id)).iterdir():
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



def top_level_names(path):
    """The names a front-end script declares at its top level (unindented const, let and function)."""
    return set(re.findall(r"^(?:async\s+)?(?:function\s+|const\s+|let\s+)([A-Za-z_$][\w$]*)", path.read_text(), re.M))


def test_the_shared_page_declares_no_name_that_only_the_app_also_declares():
    """The scripts share in one global scope, so a template both pages load reaches whichever page's version of a
    name is there. A name declared on both pages, by scripts the other doesn't load, is easy to call by mistake."""
    _, shared = share_page_scripts()
    shared = {src.removeprefix("/s/static/") for src in shared}
    app = {src.removeprefix("/static/") for src in re.findall(r'<script src="([^"]+)"', (PUBLIC_DIR / "index.html").read_text())}
    app_only = set().union(*(top_level_names(PUBLIC_DIR / src) for src in app - shared))
    share_only = set().union(*(top_level_names(PUBLIC_DIR / src) for src in shared - app))
    assert share_only and app_only
    assert share_only & app_only == set()


def test_the_shared_page_does_not_load_the_app_garment_page():
    """garmentPage.js draws edit, mend and rework buttons that call code share.html doesn't load. The share page
    gets FIELDS and displayValue from garmentFields.js instead."""
    _, scripts = share_page_scripts()
    assert "/s/static/js/templates/garmentFields.js" in scripts
    assert "/s/static/js/templates/garmentPage.js" not in scripts

# --- the demo's limit ------------------------------------------------------------------
def fill(db_path, user_id, count, expires_at="2099-01-01T00:00:00+00:00"):
    """count share rows for user_id, without photos: enough for counting."""
    for n in range(count):
        insert_share(db_path, f"filler-{user_id}-{n}", user_id, "garment", "2026-11-18T00:00:00+00:00", expires_at, {})


def test_a_limit_refuses_a_new_share_before_copying_anything(db_path, garment_id, tmp_path):
    folder = tmp_path / "shares"
    now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
    shares.share_garment(db_path, folder, 1, garment_id, "en-US", now, limit=2)
    shares.share_garment(db_path, folder, 1, garment_id, "en-US", now, limit=2)

    with pytest.raises(shares.ShareLimitReached):
        shares.share_garment(db_path, folder, 1, garment_id, "en-US", now, limit=2)
    assert len(list(folder.iterdir())) == 2


def test_expired_shares_dont_count_toward_a_limit(db_path, garment_id, tmp_path):
    fill(db_path, 1, 2, expires_at="2026-11-18T00:00:00+00:00")
    now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
    assert shares.share_garment(db_path, tmp_path / "shares", 1, garment_id, "en-US", now, limit=2) is not None


def test_the_demo_cant_have_more_than_its_limit_of_live_links(db_path):
    demo_id = insert_demo_user(db_path, "demo")
    shirt = insert_garment(db_path, demo_id, TEST_GARMENT)
    demo = Owner(User(id=demo_id, username="demo", is_demo=True))
    fill(db_path, demo_id, DEMO_SHARE_LIMIT - 1)
    make(demo, "garment", shirt)

    response = demo.post("/api/shares", json={"kind": "garment", "id": shirt})
    assert response.status_code == 409
    assert str(DEMO_SHARE_LIMIT) in response.json()["detail"]


def test_other_users_have_no_limit(owner, db_path, garment_id):
    fill(db_path, 1, DEMO_SHARE_LIMIT)
    make(owner, "garment", garment_id)


# --- the list of your links ------------------------------------------------------------
LIVE = "2099-01-01T00:00:00+00:00"
SHARE_OUT_KEYS = {"token", "path", "kind", "created_at", "expires_at", "max_expires_at", "aesthetic", "brand", "subcategory"}


def test_the_list_shows_what_each_link_is_and_nothing_else_from_it(owner, garment_id, outfit_id):
    garment_link, outfit_link = make(owner, "garment", garment_id), make(owner, "outfit", outfit_id)
    rows = {row["path"]: row for row in owner.get("/api/shares").json()}

    assert set(rows) == {garment_link["path"], outfit_link["path"]}
    for row in rows.values():
        assert set(row) == SHARE_OUT_KEYS
        assert row["path"] == f"/s/{row['token']}"
    garment_row, outfit_row = rows[garment_link["path"]], rows[outfit_link["path"]]
    assert (garment_row["kind"], garment_row["brand"], garment_row["subcategory"], garment_row["aesthetic"]) == \
           ("garment", "Kapital", TEST_GARMENT.subcategory, None)
    assert (outfit_row["kind"], outfit_row["aesthetic"], outfit_row["brand"]) == ("outfit", "Workwear Americana", None)
    assert garment_row["expires_at"] == garment_link["expires_at"]


def test_the_list_has_only_your_live_links_newest_first(owner, db_path):
    kim = insert_user(db_path, "kim", "kim@example.com")
    insert_share(db_path, "older", 1, "garment", "2026-11-17T09:00:00+00:00", LIVE, {"garment": {}})
    insert_share(db_path, "newer", 1, "garment", "2026-11-18T09:00:00+00:00", LIVE, {"garment": {}})
    insert_share(db_path, "expired", 1, "garment", "2026-11-01T09:00:00+00:00", "2026-11-04T09:00:00+00:00", {"garment": {}})
    insert_share(db_path, "kims", kim, "garment", "2026-11-18T10:00:00+00:00", LIVE, {"garment": {}})

    assert [row["token"] for row in owner.get("/api/shares").json()] == ["newer", "older"]


def test_an_admin_acting_as_someone_sees_their_links(owner, db_path):
    kim = insert_user(db_path, "kim", "kim@example.com")
    insert_share(db_path, "mine", 1, "garment", "2026-11-18T09:00:00+00:00", LIVE, {"garment": {}})
    insert_share(db_path, "kims", kim, "garment", "2026-11-18T10:00:00+00:00", LIVE, {"garment": {}})

    assert owner.put("/api/act-as", json={"user_id": kim}).status_code == 204
    assert [row["token"] for row in owner.get("/api/shares").json()] == ["kims"]


def test_listing_links_needs_a_sign_in(stranger):
    assert stranger.get("/api/shares").status_code in (401, 503)


# --- revoking a link -------------------------------------------------------------------
def token_of(link):
    return link["path"].removeprefix("/s/")


def opens(client, path):
    """Whether everything on a shared page still loads: the page, its data and its first photo."""
    data = client.get(f"{path}/data")
    if data.status_code != 200:
        return False
    first = data.json()["garment"]["photos"][0]["file"]
    return all(client.get(url).status_code == 200 for url in (path, f"{path}/photos/0/{first}", f"{path}/thumbs/0/{first}"))


def test_a_revoked_link_stops_working_and_its_photos_are_deleted(owner, stranger, garment_id):
    link = make(owner, "garment", garment_id)
    data = stranger.get(f"{link['path']}/data").json()
    photo = f"{link['path']}/photos/0/{data['garment']['photos'][0]['file']}"
    assert opens(stranger, link["path"])

    assert owner.delete(f"/api/shares/{token_of(link)}").status_code == 204

    for url in (link["path"], f"{link['path']}/data", photo):
        assert stranger.get(url).status_code == 404, url
    assert not (config.SHARES_DIR / token_of(link)).exists()
    assert owner.get("/api/shares").json() == []


def test_revoking_a_link_that_doesnt_exist_is_a_404(owner):
    assert owner.delete("/api/shares/no-such-token").status_code == 404


def test_you_cant_revoke_someone_elses_link(owner, stranger, db_path, garment_id):
    link = make(owner, "garment", garment_id)
    kim = Owner(User(id=insert_user(db_path, "kim", "kim@example.com"), username="kim"))

    assert kim.delete(f"/api/shares/{token_of(link)}").status_code == 404
    assert opens(stranger, link["path"])


def test_revoking_one_link_leaves_the_others_working(owner, stranger, garment_id):
    first, second = make(owner, "garment", garment_id), make(owner, "garment", garment_id)

    assert owner.delete(f"/api/shares/{token_of(first)}").status_code == 204
    assert opens(stranger, second["path"])
    assert [row["path"] for row in owner.get("/api/shares").json()] == [second["path"]]


def test_an_expired_link_cant_be_revoked(db_path, garment_id, tmp_path):
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    token, _ = shares.share_garment(db_path, tmp_path / "shares", 1, garment_id, "en-US", now)
    assert not shares.revoke(db_path, tmp_path / "shares", 1, token, now + timedelta(days=3))


def test_revoking_needs_a_sign_in(stranger, owner, garment_id):
    link = make(owner, "garment", garment_id)
    assert stranger.delete(f"/api/shares/{token_of(link)}").status_code in (401, 503)
    assert opens(stranger, link["path"])


# --- extending a link ------------------------------------------------------------------
MADE = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)   # every share below is made at this moment
LIMIT = "2026-11-13T12:00:00+00:00"                      # 12 days later


def iso(moment):
    return moment.isoformat(timespec="seconds")


@pytest.fixture
def made(db_path, garment_id, tmp_path):
    """A garment link made at MADE: its token."""
    token, _ = shares.share_garment(db_path, tmp_path / "shares", 1, garment_id, "en-US", MADE)
    return token


def test_extending_makes_a_link_last_72_hours_from_now(db_path, made):
    now = MADE + timedelta(days=2, hours=5)
    assert shares.extend(db_path, 1, made, now) == iso(now + timedelta(hours=72))


def test_extending_stops_at_12_days_after_the_link_was_made(db_path, made):
    now = MADE + timedelta(days=2)
    for _ in range(3):   # each extension moves "now" on 2.9 days, keeping the link live
        shares.extend(db_path, 1, made, now)
        now += timedelta(days=2, hours=22)
    assert now + timedelta(hours=72) > datetime.fromisoformat(LIMIT)   # 72 hours from now would pass the limit
    assert shares.extend(db_path, 1, made, now) == LIMIT


def test_a_link_at_its_limit_cant_be_extended(db_path, made):
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("UPDATE shares SET expires_at = ? WHERE token = ?", (LIMIT, made))
    with pytest.raises(shares.ShareAtMaxLifetime):
        shares.extend(db_path, 1, made, MADE + timedelta(days=11))


def test_extending_never_makes_a_link_shorter(db_path, made, monkeypatch):
    """Say the lifetime is cut to 1 day later on: extending a link made under 3 days mustn't shorten it."""
    monkeypatch.setattr(shares, "SHARE_LIFETIME_DAYS", 1)
    assert shares.extend(db_path, 1, made, MADE + timedelta(hours=1)) == iso(MADE + timedelta(hours=72))


def test_an_expired_link_cant_be_extended_back_to_life(db_path, made):
    expired = MADE + timedelta(hours=72)
    assert shares.extend(db_path, 1, made, expired) is None
    assert shares.load(db_path, made, expired) is None


def test_an_extended_link_works_past_its_old_expiry(db_path, made):
    old_expiry = MADE + timedelta(hours=72)
    shares.extend(db_path, 1, made, MADE + timedelta(days=2))
    assert shares.load(db_path, made, old_expiry + timedelta(hours=1)) is not None


def test_the_extend_endpoint_returns_the_updated_row(owner, garment_id):
    link = make(owner, "garment", garment_id)
    response = owner.post(f"/api/shares/{token_of(link)}/extend")
    assert response.status_code == 200
    row = response.json()
    assert set(row) == SHARE_OUT_KEYS
    assert row["expires_at"] >= link["expires_at"]
    created = datetime.fromisoformat(row["created_at"])
    assert row["max_expires_at"] == iso(created + timedelta(days=12))


def test_extending_a_link_that_doesnt_exist_is_a_404(owner):
    assert owner.post("/api/shares/no-such-token/extend").status_code == 404


def test_extending_a_link_at_its_limit_is_a_409(owner, db_path):
    now = datetime.now(timezone.utc)
    created = now - timedelta(days=11)
    insert_share(db_path, "old-link", 1, "garment", iso(created), iso(created + timedelta(days=12)), {"garment": {}})
    response = owner.post("/api/shares/old-link/extend")
    assert response.status_code == 409
    assert "12 days" in response.json()["detail"]


def test_you_cant_extend_someone_elses_link(owner, db_path, garment_id):
    link = make(owner, "garment", garment_id)
    kim = Owner(User(id=insert_user(db_path, "kim", "kim@example.com"), username="kim"))
    assert kim.post(f"/api/shares/{token_of(link)}/extend").status_code == 404
    assert owner.get("/api/shares").json()[0]["expires_at"] == link["expires_at"]


def test_extending_needs_a_sign_in(stranger, owner, garment_id):
    link = make(owner, "garment", garment_id)
    assert stranger.post(f"/api/shares/{token_of(link)}/extend").status_code in (401, 503)

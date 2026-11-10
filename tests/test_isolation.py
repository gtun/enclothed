"""Two users, one database: neither can read or change anything of the other's."""
import json
import re
import sqlite3
from contextlib import closing
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from PIL import Image

from enclothed import config
from enclothed import api, photos
from enclothed.auth import signed_in_user
from enclothed.config import MIGRATIONS_DIR, SCHEMA_PATH
from enclothed.db import init_db, insert_garment, insert_look, insert_outfits, insert_set, insert_wear, insert_weigh, save_preferences, select_garment
from enclothed.intake import TEST_GARMENT
from enclothed.models import Draft, LookPiece, LookTags, Outfit, OutfitGarment, User, WeighVerdict

TIMESTAMP = "2026-11-04T00:00:00+00:00"
_CHECK = {"answer": True, "reason": "r"}
VERDICT = WeighVerdict.model_validate({"already_own": _CHECK, "similar": [], "makes_outfits": _CHECK, "fills_gap": _CHECK,
                                       "fits_style": _CHECK, "recommendation": "maybe", "summary": "s"})
LOOK = LookTags(title="t", summary="s", pieces=[LookPiece(category="top", subcategory="t-shirt", primary_color="white", description="d", role="r")])
ALICE = User(id=1, username="alice")
BOB = User(id=2, username="bob")


def add_wardrobe(db_path, garments_dir, user_id):
    """One garment with a photo, one set, one outfit."""
    garment_id = insert_garment(db_path, user_id, TEST_GARMENT)
    second_id = insert_garment(db_path, user_id, TEST_GARMENT)
    folder = garments_dir / str(garment_id)
    folder.mkdir(parents=True)
    Image.new("RGB", (20, 20)).save(folder / "front_00.jpg")
    set_id = insert_set(db_path, user_id, [second_id], "suit")
    outfit = Outfit(aesthetic="a", explanation="e", garments=[OutfitGarment(garment_id=garment_id, styling_advice=None)])
    [outfit_id] = insert_outfits(db_path, user_id, [outfit], None, "dinner", TIMESTAMP)
    candidate_id = insert_garment(db_path, user_id, TEST_GARMENT.model_copy(update={"weighed_on": date(2026, 11, 8)}))
    insert_weigh(db_path, user_id, candidate_id, VERDICT, TIMESTAMP)
    look_id = insert_look(db_path, user_id, LOOK, None, TIMESTAMP)
    look_folder = photos.LOOKS_DIR / str(look_id)
    look_folder.mkdir(parents=True)
    Image.new("RGB", (20, 20)).save(look_folder / "00.jpg")
    return {"garment": garment_id, "second": second_id, "set": set_id, "outfit": outfit_id, "candidate": candidate_id, "look": look_id}


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute("UPDATE users SET username = 'alice' WHERE id = 1")
            conn.execute("INSERT INTO users (id, username) VALUES (2, 'bob')")
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(api, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(api, "THUMBS_DIR", tmp_path / "thumbs")
    monkeypatch.setattr(api, "INTAKE_DIR", tmp_path / "intake")
    monkeypatch.setattr(api, "OUTFIT_LOG_PATH", tmp_path / "outfit_log.jsonl")
    monkeypatch.setattr(api, "PREFERENCES_LOG_PATH", tmp_path / "preferences_log.jsonl")
    monkeypatch.setattr(photos, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(photos, "THUMBS_DIR", tmp_path / "thumbs")
    monkeypatch.setattr(photos, "LOOKS_DIR", tmp_path / "looks")
    return path


@pytest.fixture
def alice_data(db_path, tmp_path):
    return add_wardrobe(db_path, tmp_path / "garments", 1)


@pytest.fixture
def bob_data(db_path, tmp_path):
    return add_wardrobe(db_path, tmp_path / "garments", 2)


@pytest.fixture
def as_user():
    def sign_in(user):
        api.app.dependency_overrides[signed_in_user] = lambda: user
        return TestClient(api.app)
    yield sign_in
    api.app.dependency_overrides.clear()


@pytest.fixture
def bob(as_user, db_path):
    return as_user(BOB)


# --- Bob asks for Alice's things by id --------------------------------------------------
TARGETED = [
    ("GET", "/api/garments/{garment}", None),
    ("PATCH", "/api/garments/{garment}", {"notes": "bob was here"}),
    ("GET", "/api/outfits/{outfit}", None),
    ("PATCH", "/api/outfits/{outfit}", {"liked": True}),
    ("GET", "/photos/{garment}/front_00.jpg", None),
    ("GET", "/thumbs/{garment}/front_00.jpg", None),
    ("POST", "/api/weighs/{candidate}/buy", None),
    ("GET", "/looks/{look}/00.jpg", None),
    ("GET", "/looks/{look}/thumbs/00.jpg", None),
]


@pytest.mark.parametrize("method, path, body", TARGETED)
def test_someone_elses_item_is_404(bob, alice_data, bob_data, method, path, body):
    url = path.format(**alice_data)
    assert bob.request(method, url, json=body).status_code == 404


@pytest.mark.parametrize("method, path, body", TARGETED)
def test_your_own_item_still_works(bob, alice_data, bob_data, method, path, body):
    url = path.format(**bob_data)
    assert bob.request(method, url, json=body).status_code == 200


def test_every_route_with_an_id_is_covered():
    """A new route with an id in its path has to be added to TARGETED."""
    covered = {(method, re.sub(r"\{\w+\}", "{}", re.sub(r"\w+\.jpg$", "{}", path))) for method, path, _ in TARGETED}
    found = set()
    for route in api.app.routes:
        if isinstance(route, APIRoute) and "{" in route.path:
            for method in route.methods - {"HEAD", "OPTIONS"}:
                found.add((method, re.sub(r"\{\w+\}", "{}", route.path)))
    assert found - COVERED_ELSEWHERE == covered


COVERED_ELSEWHERE = {   # these don't answer 200, so they have their own tests below
    ("POST", "/api/garments/{}/mend"),
    ("POST", "/api/garments/drafts/{}"),
    ("DELETE", "/api/garments/drafts/{}"),
    ("DELETE", "/api/weighs/{}"),
    ("POST", "/api/outfits/{}/wears"),        # 201
    ("DELETE", "/api/outfits/{}/wears/{}"),   # needs a wear ID too
    ("POST", "/api/looks/{}/recreations"),    # 201, after an AI call
    ("DELETE", "/api/looks/{}"),              # 204
}


def test_someone_elses_look_cant_be_matched_or_deleted(bob, alice_data, bob_data, db_path, tmp_path):
    assert bob.post(f"/api/looks/{alice_data['look']}/recreations").status_code == 404
    assert bob.delete(f"/api/looks/{alice_data['look']}").status_code == 404
    assert (tmp_path / "looks" / str(alice_data["look"]) / "00.jpg").is_file()
    assert [look["id"] for look in bob.get("/api/looks").json()] == [bob_data["look"]]
    assert bob.delete(f"/api/looks/{bob_data['look']}").status_code == 204


def test_someone_elses_outfit_cant_be_worn_or_unworn(bob, alice_data, bob_data, db_path):
    alice_wear = insert_wear(db_path, 1, alice_data["outfit"], date(2026, 11, 8))
    assert bob.post(f"/api/outfits/{alice_data['outfit']}/wears", json={}).status_code == 404
    assert bob.delete(f"/api/outfits/{alice_data['outfit']}/wears/{alice_wear}").status_code == 404
    # nor by pairing Alice's wear with Bob's own outfit
    assert bob.delete(f"/api/outfits/{bob_data['outfit']}/wears/{alice_wear}").status_code == 404
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM wears").fetchone()[0] == 1
    assert bob.post(f"/api/outfits/{bob_data['outfit']}/wears", json={}).status_code == 201


def test_someone_elses_candidate_cant_be_discarded(bob, alice_data, bob_data, db_path):
    assert bob.delete(f"/api/weighs/{alice_data['candidate']}").status_code == 404
    assert select_garment(db_path, 1, alice_data["candidate"]) is not None
    assert bob.delete(f"/api/weighs/{bob_data['candidate']}").status_code == 204


def test_weighs_list_only_your_own(bob, alice_data, bob_data):
    assert [w["garment_id"] for w in bob.get("/api/weighs").json()] == [bob_data["candidate"]]


def test_someone_elses_garment_cant_be_mended(bob, alice_data, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert bob.post(f"/api/garments/{alice_data['garment']}/mend").status_code == 404


def test_someone_elses_draft_cant_be_accepted_or_discarded(bob, db_path, tmp_path):
    folder = tmp_path / "intake" / "drafts" / "1" / ("a" * 32)
    folder.mkdir(parents=True)
    draft = Draft(id="a" * 32, garment=TEST_GARMENT, photos=[])
    (folder / "draft.json").write_text(draft.model_dump_json())

    assert bob.post(f"/api/garments/drafts/{draft.id}", json=TEST_GARMENT.model_dump(mode="json")).status_code == 404
    bob.delete(f"/api/garments/drafts/{draft.id}")

    assert (folder / "draft.json").exists()


def test_a_failed_edit_leaves_the_garment_alone(bob, alice_data, db_path):
    bob.patch(f"/api/garments/{alice_data['garment']}", json={"notes": "bob was here"})
    assert select_garment(db_path, 1, alice_data["garment"]).notes != "bob was here"


def test_a_failed_like_leaves_the_outfit_alone(bob, as_user, alice_data):
    bob.patch(f"/api/outfits/{alice_data['outfit']}", json={"liked": True})
    alice = as_user(ALICE)
    assert alice.get(f"/api/outfits/{alice_data['outfit']}").json()["liked"] is None


# --- Lists show only your own ------------------------------------------------------------
def ids(items):
    return [item["id"] for item in items]


def test_lists_show_only_your_own(bob, alice_data, bob_data):
    assert ids(bob.get("/api/garments").json()) == [bob_data["garment"], bob_data["second"], bob_data["candidate"]]
    assert ids(bob.get("/api/outfits").json()) == [bob_data["outfit"]]
    assert ids(bob.get("/api/sets").json()) == [bob_data["set"]]


def test_a_new_user_starts_empty(bob, alice_data):
    assert bob.get("/api/garments").json() == []
    assert bob.get("/api/outfits").json() == []
    assert bob.get("/api/sets").json() == []
    assert bob.get("/api/preferences").json() == {"text": None, "updated_at": None}


def test_preferences_are_separate(bob, db_path):
    save_preferences(db_path, 1, "alice's notes", TIMESTAMP)
    assert bob.get("/api/preferences").json()["text"] is None
    bob.put("/api/preferences", json={"text": "bob's notes"})
    assert bob.get("/api/preferences").json()["text"] == "bob's notes"


def test_profile_is_your_own(bob):
    assert bob.get("/api/profile").json()["name"] == "bob"


# --- Using someone else's garment in your own records ------------------------------------
def test_suggestions_reject_someone_elses_anchor(bob, alice_data, bob_data):
    response = bob.post("/api/outfits/suggestions", json={"anchors": [alice_data["garment"]], "details": ""})
    assert response.status_code == 422


def test_saving_an_outfit_rejects_someone_elses_garment(bob, alice_data, bob_data):
    response = bob.post("/api/outfits", json={
        "aesthetic": "a", "explanation": "e", "garments": [{"garment_id": alice_data["garment"]}],
    })
    assert response.status_code == 422


def test_the_llm_only_sees_your_own_wardrobe(bob, alice_data, bob_data, monkeypatch):
    seen = {}

    def fake_generate(db_path, user_id, wardrobe, *args, **kwargs):
        seen["user_id"], seen["wardrobe"] = user_id, set(wardrobe)
        return None, []

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(api, "generate_outfits", fake_generate)
    bob.post("/api/outfits/suggestions", json={"anchors": [], "details": "dinner"})
    assert seen == {"user_id": 2, "wardrobe": {bob_data["garment"], bob_data["second"]}}


def test_suggestion_logs_record_the_user(bob, bob_data, monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr("enclothed.outfit.recommend_outfits", lambda client, context, language: (_empty_result(), None))
    bob.post("/api/outfits/suggestions", json={"anchors": [], "details": "dinner"})
    entry = json.loads((tmp_path / "outfit_log.jsonl").read_text().splitlines()[0])
    assert entry["user_id"] == 2


def _empty_result():
    from enclothed.models import OutfitResult
    return OutfitResult(outfits=[])


# --- Photos and Cloudflare ----------------------------------------------------------------
@pytest.mark.parametrize("path", ["/photos/{garment}/front_00.jpg", "/thumbs/{garment}/front_00.jpg"])
def test_photos_stay_out_of_shared_caches(bob, bob_data, path):
    response = bob.get(path.format(**bob_data))
    assert response.headers["cache-control"].startswith("private")


@pytest.mark.parametrize("path", ["/photos/{garment}/missing.jpg", "/photos/{garment}/..%2F..%2Ftest.db", "/photos/{garment}/.hidden"])
def test_bad_photo_names_are_404(bob, bob_data, path):
    assert bob.get(path.format(**bob_data)).status_code == 404


def test_photos_need_sign_in(tmp_path, db_path, alice_data, monkeypatch):
    monkeypatch.delenv("ENCLOTHED_DEV_USER", raising=False)
    monkeypatch.setenv("ACCESS_TEAM_NAME", "team")
    monkeypatch.setenv("AUD_TAG", "aud")
    client = TestClient(api.app)
    assert client.get(f"/photos/{alice_data['garment']}/front_00.jpg").status_code == 401
    assert client.get(f"/thumbs/{alice_data['garment']}/front_00.jpg").status_code == 401


def test_preference_rewrites_log_the_user(bob, monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    usage = SimpleNamespace(model_dump=lambda: {})
    monkeypatch.setattr(api, "improve_preferences", lambda client, text: ("better", usage))
    bob.post("/api/preferences/improve", json={"text": "tidy this"})
    entry = json.loads((tmp_path / "preferences_log.jsonl").read_text().splitlines()[0])
    assert entry["user_id"] == 2


# --- acting as another user ----------------------------------------------------------------
ADMIN = User(id=1, username="alice", is_admin=True)


@pytest.fixture
def admin(as_user, db_path, monkeypatch):
    monkeypatch.setattr("enclothed.auth.config.DB_PATH", db_path)
    return as_user(ADMIN)


def test_admin_can_act_as_someone_and_come_back(admin, alice_data, bob_data):
    assert admin.put("/api/act-as", json={"user_id": 2}).status_code == 204
    assert ids(admin.get("/api/garments").json()) == [bob_data["garment"], bob_data["second"], bob_data["candidate"]]
    assert admin.get("/api/profile").json() == {"name": "bob", "language": "en-US", "is_admin": True, "signed_in_as": "alice", "is_demo": False, "demo_user_id": None}

    admin.put("/api/act-as", json={"user_id": None})
    assert ids(admin.get("/api/garments").json()) == [alice_data["garment"], alice_data["second"], alice_data["candidate"]]
    assert admin.get("/api/profile").json()["signed_in_as"] is None


def test_admin_acting_as_someone_sees_their_photos(admin, bob_data):
    admin.put("/api/act-as", json={"user_id": 2})
    assert admin.get(f"/photos/{bob_data['garment']}/front_00.jpg").status_code == 200


def test_admin_acting_as_someone_writes_to_their_wardrobe(admin):
    admin.put("/api/act-as", json={"user_id": 2})
    admin.put("/api/preferences", json={"text": "set by admin"})
    admin.put("/api/act-as", json={"user_id": None})
    assert admin.get("/api/preferences").json()["text"] is None


def test_acting_as_an_unknown_user_is_404(admin):
    assert admin.put("/api/act-as", json={"user_id": 99}).status_code == 404


def test_a_stale_cookie_falls_back_to_yourself(admin):
    admin.cookies.set("enclothed_act_as", "99")
    assert admin.get("/api/profile").json()["name"] == "alice"


def test_a_garbled_cookie_falls_back_to_yourself(admin):
    admin.cookies.set("enclothed_act_as", "not-a-number")
    assert admin.get("/api/profile").json()["name"] == "alice"


def test_admin_lists_users(admin):
    assert admin.get("/api/users").json() == [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}]


def test_acting_keeps_the_admin_list_available(admin):
    admin.put("/api/act-as", json={"user_id": 2})
    assert admin.get("/api/users").status_code == 200


def test_non_admin_cannot_list_users(bob):
    assert bob.get("/api/users").status_code == 403


def test_non_admin_cannot_act_as_anyone(bob, alice_data):
    assert bob.put("/api/act-as", json={"user_id": 1}).status_code == 403


def test_a_forged_cookie_does_nothing_for_a_non_admin(bob, alice_data, bob_data):
    bob.cookies.set("enclothed_act_as", "1")
    assert ids(bob.get("/api/garments").json()) == [bob_data["garment"], bob_data["second"], bob_data["candidate"]]
    assert bob.get(f"/api/garments/{alice_data['garment']}").status_code == 404

"""The shared demo wardrobe: who can reach it, what it holds, its reset, and its token limit."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from enclothed import api, config, db, demo, main, photos
from enclothed import outfit as outfit_module
from enclothed.auth import signed_in_user
from enclothed.intake import TEST_GARMENT
from enclothed.models import Outfit, OutfitGarment, OutfitResult, User

ALICE = User(id=1, username="alice", is_admin=True)
BOB = User(id=2, username="bob", language="zh-TW")
NOON = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def add_garment(db_path, user_id, category="top", subcategory="t-shirt", photo=True, **fields):
    garment = TEST_GARMENT.model_copy(update={"category": category, "subcategory": subcategory, **fields})
    garment_id = db.insert_garment(db_path, user_id, garment)
    if photo:
        folder = photos.GARMENTS_DIR / str(garment_id)
        folder.mkdir(parents=True)
        Image.new("RGB", (20, 20)).save(folder / "front_00.jpg")
    return garment_id


def add_outfit(db_path, user_id, garment_ids, request="dinner with my boss", liked=None):
    outfit = Outfit(aesthetic="Clean", explanation="Works.", garments=[OutfitGarment(garment_id=i, styling_advice="Tuck it") for i in garment_ids])
    [outfit_id] = db.insert_outfits(db_path, user_id, [outfit], None, request, "2026-11-01T12:00:00+00:00")
    if liked is not None:
        db.set_outfit_liked(db_path, user_id, outfit_id, liked)
    return outfit_id


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    assert db.insert_user(path, "bob", "bob@example.com", False, "zh-TW") == 2
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "DEMO_TEMPLATE_DIR", tmp_path / "demo-template")
    monkeypatch.setattr(api, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(api, "INTAKE_DIR", tmp_path / "intake")
    monkeypatch.setattr(api, "TAGGING_LOG_PATH", tmp_path / "tagging_log.jsonl")
    monkeypatch.setattr(api, "OUTFIT_LOG_PATH", tmp_path / "outfit_log.jsonl")
    monkeypatch.setattr(api, "PREFERENCES_LOG_PATH", tmp_path / "preferences_log.jsonl")
    monkeypatch.setattr(photos, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(photos, "THUMBS_DIR", tmp_path / "thumbs")
    (tmp_path / "garments").mkdir()
    return path


@pytest.fixture
def seeded(db_path):
    """Alice's wardrobe, copied into the demo: one outfit, a set, and a garment with private notes."""
    shirt = add_garment(db_path, 1, "top", "t-shirt", notes="Gift from my ex")
    pants = add_garment(db_path, 1, "bottom", "jeans")
    shoes = add_garment(db_path, 1, "shoes", "loafers")
    jacket = add_garment(db_path, 1, "outerwear", "suit jacket")
    trousers = add_garment(db_path, 1, "bottom", "dress trousers")
    db.insert_set(db_path, 1, [jacket, trousers], "Grey suit")
    db.save_preferences(db_path, 1, "I never wear green", "2026-11-01T12:00:00+00:00")
    add_outfit(db_path, 1, [shirt, pants, shoes], liked=1)
    demo.seed(db_path, 1, per_category=5, max_outfits=8)
    return {"demo": db.select_demo_user(db_path), "shirt": shirt}


@pytest.fixture
def as_user():
    def sign_in(user):
        api.app.dependency_overrides[signed_in_user] = lambda: user
        return TestClient(api.app)
    yield sign_in
    api.app.dependency_overrides.clear()


@pytest.fixture
def bob_in_demo(seeded, as_user):
    client = as_user(BOB)
    assert client.put("/api/act-as", json={"user_id": seeded["demo"].id}).status_code == 204
    return client


# --- reaching the demo ------------------------------------------------------------------
def test_anyone_signed_in_can_open_the_demo_and_leave(bob_in_demo, seeded):
    profile = bob_in_demo.get("/api/profile").json()
    assert profile["is_demo"] and profile["signed_in_as"] == "bob" and profile["name"] == "demo"
    assert len(bob_in_demo.get("/api/garments").json()) == 5
    bob_in_demo.put("/api/act-as", json={"user_id": None})
    assert bob_in_demo.get("/api/garments").json() == []


def test_a_non_admin_still_cant_open_a_real_wardrobe(seeded, as_user):
    assert as_user(BOB).put("/api/act-as", json={"user_id": 1}).status_code == 403


def test_a_forged_cookie_reaches_the_demo_but_not_a_real_wardrobe(seeded, as_user):
    client = as_user(BOB)
    client.cookies.set("enclothed_act_as", "1")
    assert client.get("/api/garments").json() == []


def test_the_profile_offers_the_demo_only_once_it_exists(db_path, as_user):
    assert as_user(BOB).get("/api/profile").json()["demo_user_id"] is None


def test_nobody_can_sign_in_as_the_demo(seeded):
    assert seeded["demo"].email is None


def test_the_demo_is_the_only_wardrobe_visitors_change(bob_in_demo, seeded, db_path):
    garment = bob_in_demo.get("/api/garments").json()[0]
    assert bob_in_demo.patch(f"/api/garments/{garment['id']}", json={"brand": "Visitor"}).status_code == 200
    assert all(g.brand != "Visitor" for g in db.select_all_garments(db_path, 1))


def test_the_demo_uses_the_visitors_language_and_changing_it_changes_theirs(bob_in_demo, db_path):
    assert bob_in_demo.get("/api/profile").json()["language"] == "zh-TW"
    assert bob_in_demo.get("/api/options").json()["color_labels"]["black"] == "黑色"
    assert bob_in_demo.put("/api/language", json={"language": "ja-JP"}).status_code == 204
    assert db.select_user(db_path, 2).language == "ja-JP"
    assert db.select_demo_user(db_path).language == "en-US"


# --- what goes in it --------------------------------------------------------------------
def test_private_things_stay_out(seeded, db_path):
    demo_id = seeded["demo"].id
    assert all(g.notes is None for g in db.select_all_garments(db_path, demo_id))
    assert db.select_preferences(db_path, demo_id) is None
    assert all(o["prompt_message"] == config.DEMO_OUTFIT_REQUEST for o in db.select_all_outfits(db_path, demo_id))
    saved = (config.DEMO_TEMPLATE_DIR / demo.TEMPLATE_FILE).read_text(encoding="utf-8")
    assert "Gift from my ex" not in saved and "dinner with my boss" not in saved


def test_the_demo_is_a_copy_with_its_own_ids(seeded, db_path):
    demo_id = seeded["demo"].id
    real_ids = {g.id for g in db.select_all_garments(db_path, 1)}
    garments = db.select_all_garments(db_path, demo_id)
    assert real_ids.isdisjoint(g.id for g in garments)
    assert all(g.user_id == demo_id for g in garments)
    assert all((photos.GARMENTS_DIR / str(g.id) / "front_00.jpg").exists() for g in garments)


def test_sets_and_liked_outfits_come_across(seeded, db_path):
    demo_id = seeded["demo"].id
    assert list(db.select_all_sets(db_path, demo_id).values()) == ["Grey suit"]
    [outfit] = db.select_all_outfits(db_path, demo_id)
    assert outfit["liked"] == 1
    assert {g["garment_id"] for g in outfit["garments"]} <= {g.id for g in db.select_all_garments(db_path, demo_id)}


def test_a_sample_mixes_categories_and_tries_each_subcategory_first():
    garments = [TEST_GARMENT.model_copy(update={"id": i, "category": "top", "subcategory": s})
                for i, s in enumerate(["t-shirt", "t-shirt", "t-shirt", "hoodie", "polo"], start=1)]
    garments.append(TEST_GARMENT.model_copy(update={"id": 6, "category": "shoes", "subcategory": "loafers"}))
    sample, _ = demo.choose_sample(garments, [], per_category=3, max_outfits=0)
    assert sorted(g.id for g in sample) == [1, 4, 5, 6]


def test_a_sample_skips_disliked_outfits_and_ones_with_missing_garments():
    garments = [TEST_GARMENT.model_copy(update={"id": 1})]
    entry = lambda i: {"garment_id": i, "styling_advice": None, "is_anchor": 0}
    outfits = [
        {"id": 1, "liked": 0, "garments": [entry(1)]},
        {"id": 2, "liked": None, "garments": [entry(1), entry(9)]},
        {"id": 3, "liked": None, "garments": [entry(1)]},
        {"id": 4, "liked": 1, "garments": [entry(1)]},
    ]
    _, picked = demo.choose_sample(garments, outfits, per_category=0, max_outfits=2)
    assert [o["id"] for o in picked] == [4, 3]


def test_garments_with_no_photos_stay_out(db_path):
    add_garment(db_path, 1, photo=False)
    kept = add_garment(db_path, 1, "shoes", "loafers")
    template = demo.seed(db_path, 1, 5, 8)
    assert [g["source_id"] for g in template["garments"]] == [kept]


# --- the daily reset --------------------------------------------------------------------
@pytest.mark.parametrize("hour, expected", [(12, datetime(2026, 11, 5, 8, tzinfo=timezone.utc)), (3, datetime(2026, 11, 4, 8, tzinfo=timezone.utc))])
def test_last_reset_time(hour, expected):
    assert demo.last_reset_time(NOON.replace(hour=hour)) == expected


def expire(db_path, demo_id):
    db.clear_demo_reset(db_path, demo_id)


def test_reset_removes_what_visitors_added(seeded, db_path, bob_in_demo):
    demo_id = seeded["demo"].id
    extra = add_garment(db_path, demo_id, "shoes", "tabi")
    Image.new("RGB", (5, 5)).save(photos.GARMENTS_DIR / str(extra) / "other_00.jpg")
    db.save_preferences(db_path, demo_id, "visitor text", "2026-11-05T12:00:00+00:00")
    expire(db_path, demo_id)

    assert len(bob_in_demo.get("/api/garments").json()) == 5   # opening it triggers the reset
    assert not (photos.GARMENTS_DIR / str(extra)).exists()
    assert db.select_preferences(db_path, demo_id) is None


def test_reset_never_touches_real_wardrobes(seeded, db_path):
    demo_id = seeded["demo"].id
    bob_garment = add_garment(db_path, 2, "shoes", "tabi")
    before = [g.model_dump() for g in db.select_all_garments(db_path, 1)]
    outfits_before = db.select_all_outfits(db_path, 1)
    demo.reset_wardrobe(db_path, demo_id, config.DEMO_TEMPLATE_DIR, "2026-11-05T12:00:00+00:00")

    assert [g.model_dump() for g in db.select_all_garments(db_path, 1)] == before
    assert db.select_all_outfits(db_path, 1) == outfits_before
    assert db.select_preferences(db_path, 1)[0] == "I never wear green"
    assert db.select_garment(db_path, 2, bob_garment) is not None
    assert all((photos.GARMENTS_DIR / str(g["id"]) / "front_00.jpg").exists() for g in before)


@pytest.mark.parametrize("user_id", [1, 2, 99])
def test_only_the_demo_user_can_be_wiped(seeded, db_path, user_id):
    with pytest.raises(ValueError):
        db.delete_demo_wardrobe(db_path, user_id, set())
    assert len(db.select_all_garments(db_path, 1)) == 5


def test_reset_keeps_ids_and_photo_folders_but_undoes_edits(seeded, db_path, bob_in_demo):
    """The NAS backup never deletes, so new folders every day would pile up there."""
    demo_id = seeded["demo"].id
    before = db.select_all_garments(db_path, demo_id)
    client_garment = before[0]
    bob_in_demo.patch(f"/api/garments/{client_garment.id}", json={"brand": "Visitor", "disowned_on": "2026-11-05"})
    demo.reset_wardrobe(db_path, demo_id, config.DEMO_TEMPLATE_DIR, "2026-11-05T12:00:00+00:00")

    after = db.select_all_garments(db_path, demo_id)
    assert [g.id for g in after] == [g.id for g in before]
    assert after[0].brand == client_garment.brand and after[0].disowned_on is None
    assert all((photos.GARMENTS_DIR / str(g.id) / "front_00.jpg").exists() for g in after)


def test_seeding_again_replaces_the_old_sample(seeded, db_path):
    """SQLite can reuse the deleted ids, so check the folders match the rows rather than the ids."""
    demo_id = seeded["demo"].id
    demo.seed(db_path, 1, per_category=1, max_outfits=0)
    rows = {g.id for user_id in (1, demo_id) for g in db.select_all_garments(db_path, user_id)}
    assert {int(folder.name) for folder in photos.GARMENTS_DIR.iterdir()} == rows
    assert db.select_all_outfits(db_path, demo_id) == []


def test_leftover_photos_are_kept_and_stay_out_of_the_demo(db_path):
    """A folder can outlive its garment's row, and SQLite then hands that id to the next garment."""
    garment = add_garment(db_path, 1, "shoes", "loafers")
    leftover = photos.GARMENTS_DIR / str(garment + 1)
    leftover.mkdir()
    Image.new("RGB", (5, 5)).save(leftover / "private.jpg")

    demo.seed(db_path, 1, 5, 8)

    [copy] = db.select_all_garments(db_path, db.select_demo_user(db_path).id)
    assert copy.id == garment + 1
    assert [p.name for p in (photos.GARMENTS_DIR / str(copy.id)).iterdir()] == ["front_00.jpg"]
    [kept] = (photos.GARMENTS_DIR.parent / "orphaned-photos").iterdir()
    assert (kept / "private.jpg").exists()


def test_a_half_built_demo_isnt_offered(seeded, db_path, as_user):
    assert as_user(BOB).get("/api/profile").json()["demo_user_id"] == seeded["demo"].id
    db.clear_demo_reset(db_path, seeded["demo"].id)
    assert as_user(BOB).get("/api/profile").json()["demo_user_id"] is None


def test_the_template_outlives_a_reset(seeded, db_path):
    for _ in range(2):
        demo.reset_wardrobe(db_path, seeded["demo"].id, config.DEMO_TEMPLATE_DIR, "2026-11-05T12:00:00+00:00")
    assert len(db.select_all_garments(db_path, seeded["demo"].id)) == 5


def test_refresh_runs_once_a_day(seeded, db_path, monkeypatch):
    runs = []
    monkeypatch.setattr(demo, "reset_wardrobe", lambda *args: runs.append(args))
    user = seeded["demo"]
    expire(db_path, user.id)
    stale = db.select_demo_user(db_path)
    demo.refresh(db_path, stale, NOON)
    demo.refresh(db_path, stale, NOON + timedelta(hours=1))         # a second request with the old row
    demo.refresh(db_path, db.select_demo_user(db_path), NOON + timedelta(hours=2))
    assert len(runs) == 1
    demo.refresh(db_path, db.select_demo_user(db_path), NOON + timedelta(days=1))
    assert len(runs) == 2


def test_a_failed_reset_is_tried_again(seeded, db_path, monkeypatch):
    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr(demo, "reset_wardrobe", fail)
    expire(db_path, seeded["demo"].id)
    with pytest.raises(OSError):
        demo.refresh(db_path, db.select_demo_user(db_path), NOON)
    assert db.select_demo_user(db_path).demo_reset_at is None


# --- the daily token limit --------------------------------------------------------------
def spend(path, user_id, tokens, when):
    with path.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"timestamp": when.isoformat(), "user_id": user_id,
                              "usage": {"model": "claude-sonnet-5-5", "input_tokens": tokens, "output_tokens": 0}}) + "\n")


@pytest.fixture
def overspent(seeded, db_path, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    spend(tmp_path / "outfit_log.jsonl", seeded["demo"].id, config.DEMO_DAILY_TOKEN_LIMIT, datetime.now(timezone.utc))


def test_tokens_used_counts_only_the_demo_since_the_last_reset(tmp_path):
    log = tmp_path / "log.jsonl"
    spend(log, 3, 100, NOON)
    spend(log, 3, 50, NOON - timedelta(hours=5))    # before today's reset
    spend(log, 1, 999, NOON)                        # a real user
    assert demo.tokens_used({"outfits": log}, 3, NOON + timedelta(hours=1)) == 100


@pytest.mark.parametrize("request_args", [
    {"url": "/api/outfits/suggestions", "json": {"details": "dinner"}},
    {"url": "/api/preferences/improve", "json": {"text": "I like black"}},
    {"url": "/api/garments", "files": [("photos", ("a.jpg", b"x", "image/jpeg"))]},
])
def test_every_ai_route_stops_at_the_limit(bob_in_demo, overspent, request_args):
    response = bob_in_demo.post(**request_args)
    assert response.status_code == 429
    assert "allowance" in response.json()["detail"]


def test_real_wardrobes_arent_limited(seeded, db_path, as_user, tmp_path, monkeypatch):
    spend(tmp_path / "outfit_log.jsonl", 2, config.DEMO_DAILY_TOKEN_LIMIT * 2, datetime.now(timezone.utc))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(outfit_module, "recommend_outfits", lambda client, context, language: (OutfitResult(outfits=[]), None))
    assert as_user(BOB).post("/api/outfits/suggestions", json={"details": "dinner"}).status_code == 200


def test_ai_works_in_the_demo_and_writes_in_the_visitors_language(bob_in_demo, seeded, monkeypatch):
    seen = {}
    def fake(client, context, language):
        seen["language"] = language
        return OutfitResult(outfits=[]), None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(outfit_module, "recommend_outfits", fake)
    assert bob_in_demo.post("/api/outfits/suggestions", json={"details": "dinner"}).status_code == 200
    assert seen["language"] == "zh-TW"


# --- the command ------------------------------------------------------------------------
def test_demo_seed_command_can_run_twice(seeded, db_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["enclothed", "demo-seed", "--per-category", "1"])
    assert main.main() == 0
    assert main.main() == 0
    assert "Demo wardrobe ready" in capsys.readouterr().out
    assert len([u for u in db.select_all_users(db_path) if u.is_demo]) == 1

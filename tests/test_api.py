import json
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from enclothed import api, photos
from enclothed import outfit as outfit_module
from enclothed.db import init_db, insert_garment, insert_outfits, insert_set, select_owned_garments
from enclothed.fabrics import FABRIC_TYPES
from enclothed.models import Category, Color, FabricWeight, Fit, Hem, Outfit, OutfitResult, Shape, Sheen, Sleeve, Statement, SUBCATEGORIES
from enclothed.config import SCHEMA_PATH, MIGRATIONS_DIR
from enclothed.auth import signed_in_user
from enclothed.intake import TEST_GARMENT
from enclothed.models import TokenUsage, User


@pytest.fixture
def signed_in():
    """Every request counts as the owner. test_auth.py covers real sign-in."""
    api.app.dependency_overrides[signed_in_user] = lambda: User(id=1, username="owner", is_admin=True)
    yield
    api.app.dependency_overrides.clear()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """A fresh test DB, and the API pointed at it instead of the real one."""
    path = tmp_path / "test.db"
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(api, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(api, "INTAKE_DIR", tmp_path / "intake")
    monkeypatch.setattr(api, "TAGGING_LOG_PATH", tmp_path / "tagging_log.jsonl")
    monkeypatch.setattr(api, "OUTFIT_LOG_PATH", tmp_path / "outfit_log.jsonl")
    monkeypatch.setattr(api, "PREFERENCES_LOG_PATH", tmp_path / "preferences_log.jsonl")
    monkeypatch.setattr(photos, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(photos, "THUMBS_DIR", tmp_path / "thumbs")
    return path


@pytest.fixture
def client(db_path, signed_in):
    return TestClient(api.app)


@pytest.fixture
def outfit_id(db_path):
    garment_ids = [insert_garment(db_path, 1, TEST_GARMENT) for _ in range(2)]
    outfit = Outfit(
        aesthetic="test look",
        explanation="why it works",
        garments=[{"garment_id": i} for i in garment_ids],
    )
    [new_id] = insert_outfits(db_path, 1, [outfit], None, "dinner", "2026-11-01T00:00:00+00:00")
    return new_id


# --- PATCH /api/garments/{id} --------------------------------------------------------
def test_patch_cannot_change_a_garments_owner(client, db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    assert client.patch(f"/api/garments/{garment_id}", json={"user_id": 2}).status_code == 422


@pytest.mark.parametrize("text", ["Now in navy.\nSee https://example.com", ""])
def test_patch_styling_notes_persists(client, db_path, text):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    response = client.patch(f"/api/garments/{garment_id}", json={"styling_notes": text})
    assert response.status_code == 200
    assert client.get(f"/api/garments/{garment_id}").json()["styling_notes"] == text


def test_patch_styling_notes_cannot_be_null(client, db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    assert client.patch(f"/api/garments/{garment_id}", json={"styling_notes": None}).status_code == 422


# --- PATCH /api/outfits/{id} ---------------------------------------------------------

@pytest.mark.parametrize("liked", [True, False, None])
def test_patch_liked_sets_value_and_returns_outfit(client, outfit_id, liked):
    response = client.patch(f"/api/outfits/{outfit_id}", json={"liked": liked})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == outfit_id
    assert body["liked"] == liked
    assert len(body["garments"]) == 2


def test_patch_liked_persists(client, outfit_id):
    client.patch(f"/api/outfits/{outfit_id}", json={"liked": True})
    assert client.get(f"/api/outfits/{outfit_id}").json()["liked"] is True


def test_patch_liked_missing_outfit_is_404(client):
    response = client.patch("/api/outfits/999", json={"liked": True})
    assert response.status_code == 404


@pytest.mark.parametrize("body", [{}, {"liked": "maybe"}, {"liked": 5}])
def test_patch_liked_rejects_bad_body(client, outfit_id, body):
    response = client.patch(f"/api/outfits/{outfit_id}", json=body)
    assert response.status_code == 422
    assert client.get(f"/api/outfits/{outfit_id}").json()["liked"] is None


# --- GET /api/sets -------------------------------------------------------------------

def test_list_sets_empty(client):
    response = client.get("/api/sets")
    assert response.status_code == 200
    assert response.json() == []


def test_list_sets_returns_id_and_name_in_order(client, db_path):
    garment_ids = [insert_garment(db_path, 1, TEST_GARMENT) for _ in range(4)]
    suit_id = insert_set(db_path, 1, garment_ids[:2], "navy suit")
    unnamed_id = insert_set(db_path, 1, garment_ids[2:], None)

    response = client.get("/api/sets")
    assert response.status_code == 200
    assert response.json() == [
        {"id": suit_id, "name": "navy suit"},
        {"id": unnamed_id, "name": None},
    ]


# --- GET /api/options ----------------------------------------------------------------

def test_options_match_the_models(client):
    response = client.get("/api/options")
    assert response.status_code == 200
    body = response.json()

    assert body["categories"] == list(get_args(Category))
    assert [color["name"] for color in body["colors"]] == list(get_args(Color))
    assert [fit["value"] for fit in body["fits"]] == list(get_args(Fit))
    assert [sheen["value"] for sheen in body["sheens"]] == list(get_args(Sheen))
    assert [shape["value"] for shape in body["shapes"]] == list(get_args(Shape))
    assert [hem["value"] for hem in body["hems"]] == list(get_args(Hem))
    assert [weight["value"] for weight in body["fabric_weights"]] == list(get_args(FabricWeight))
    assert [sleeve["value"] for sleeve in body["sleeves"]] == list(get_args(Sleeve))
    assert [statement["value"] for statement in body["statements"]] == list(get_args(Statement))
    for category, choices in body["subcategories"].items():
        assert set(choices) == SUBCATEGORIES[category]
        assert choices[-1] == "other"


def test_fabric_options_list_every_fabric_with_other_last(client):
    fabrics = client.get("/api/options").json()["fabric_types"]
    values = [fabric["value"] for fabric in fabrics]
    assert set(values) == FABRIC_TYPES
    assert values[-1] == "other"
    assert values[:-1] == sorted(values[:-1])


def test_options_say_which_fields_apply_to_which_categories(client):
    fields = client.get("/api/options").json()["field_categories"]
    assert fields["sleeve"] == ["top", "one-piece", "outerwear"]
    assert fields["hem"] == ["top", "bottom", "one-piece", "outerwear"]
    assert "fabric_type" not in fields


def test_options_levels_are_numbered_labels(client):
    body = client.get("/api/options").json()
    assert body["formality"][0] == {"value": 1, "label": "casual"}
    assert [level["value"] for level in body["warmth"]] == [1, 2, 3, 4, 5]
    assert body["fits"][0] == {"value": "slim", "label": "slim (close to the body)"}
    assert body["sheens"][1] == {"value": "low", "label": "low (soft luster)"}


# --- GET /api/profile and the page ------------------------------------------------------

def test_profile_returns_the_signed_in_username(client):
    assert client.get("/api/profile").json() == {"name": "owner", "language": "en-US", "is_admin": True, "signed_in_as": None, "is_demo": False, "demo_user_id": None}


@pytest.mark.parametrize("path", ["/static/icons/favicon.svg", "/static/icons/favicon-32.png", "/static/icons/apple-touch-icon.png"])
def test_page_links_icons_that_are_served(client, path):
    assert path in client.get("/").text
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/static/css/theme.css", "/static/css/app.css"])
def test_stylesheets_are_served(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_root_serves_the_front_end(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>enclothed</title>" in response.text


# --- outfits from the web: suggestions and save-your-own -----------------------------

import io
from PIL import Image

from enclothed import intake, outfit as outfit_module
from enclothed.config import MANUAL_OUTFIT_REQUEST
from enclothed.models import OutfitResult, TaggingResult, PhotoTag


@pytest.fixture
def basics(db_path):
    """A wearable wardrobe: top, bottom, shoes, plus an outerwear piece. Returns their ids by category."""
    make = lambda **kw: insert_garment(db_path, 1, TEST_GARMENT.model_copy(update=kw))
    return {
        "top": make(category="top", subcategory="t-shirt"),
        "bottom": make(category="bottom", subcategory="jeans"),
        "shoes": make(category="shoes", subcategory="loafers"),
        "outerwear": make(),
    }


@pytest.fixture
def llm(monkeypatch):
    """Replace the outfit LLM call; records what it was sent and returns `llm.result`."""
    class Fake:
        result = None
        calls = []
    def fake_recommend(client, context, language="en-US"):
        Fake.calls.append(context)
        return Fake.result, None
    monkeypatch.setattr(outfit_module, "recommend_outfits", fake_recommend)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return Fake


def suggestion(ids, aesthetic="look"):
    return {"aesthetic": aesthetic, "explanation": "why", "garments": [{"garment_id": i} for i in ids]}


def test_suggestions_returns_the_new_valid_outfits(client, basics, llm):
    b = basics
    llm.result = OutfitResult.model_validate({"outfits": [
        suggestion([b["top"], b["bottom"], b["shoes"]], "A"),
        suggestion([b["top"], b["bottom"], b["shoes"], b["outerwear"]], "B"),
        suggestion([b["top"], b["shoes"]], "invalid: no bottom"),
    ]})
    response = client.post("/api/outfits/suggestions", json={"anchors": [b["shoes"]], "details": "dinner"})
    assert response.status_code == 200
    body = response.json()
    assert [o["aesthetic"] for o in body] == ["A", "B"]
    assert all(o["prompt_message"] == "dinner" for o in body)
    assert {g["garment"]["id"] for g in body[0]["garments"]} == {b["top"], b["bottom"], b["shoes"]}
    assert [g["is_anchor"] for g in body[0]["garments"] if g["garment"]["id"] == b["shoes"]] == [True]
    assert len(client.get("/api/outfits").json()) == 2


def test_suggestions_needs_anchors_or_details(client, basics, llm):
    response = client.post("/api/outfits/suggestions", json={"anchors": [], "details": "   "})
    assert response.status_code == 422
    assert llm.calls == []


def test_suggestions_rejects_unknown_anchor(client, basics, llm):
    response = client.post("/api/outfits/suggestions", json={"anchors": [999]})
    assert response.status_code == 422
    assert llm.calls == []


def test_suggestions_send_count_and_riskiness_and_return_the_tier(client, basics, llm):
    b = basics
    llm.result = OutfitResult.model_validate({"outfits": [
        {**suggestion([b["top"], b["bottom"], b["shoes"]], "A"), "risk_tier": "bold"},
        suggestion([b["top"], b["bottom"], b["shoes"]], "B"),   # tier left blank by the LLM
    ]})
    response = client.post("/api/outfits/suggestions", json={"details": "dinner", "count": 2, "riskiness": "bold"})
    assert response.status_code == 200
    assert any(block["text"] == "<options>\nSuggest exactly 2 outfits: 2 bold.\n</options>" for block in llm.calls[-1])
    assert [o["risk_tier"] for o in response.json()] == ["bold", "bold"]


def test_suggestions_default_to_three_mixed(client, basics, llm):
    b = basics
    llm.result = OutfitResult.model_validate({"outfits": [suggestion([b["top"], b["bottom"], b["shoes"]])]})
    client.post("/api/outfits/suggestions", json={"details": "dinner"})
    assert any("Suggest exactly 3 outfits: 1 safe, 1 stretch, 1 bold." in block["text"] for block in llm.calls[-1])


def test_suggestions_reject_bad_count_or_riskiness(client, basics, llm):
    for body in ({"count": 0}, {"count": 6}, {"riskiness": "wild"}):
        response = client.post("/api/outfits/suggestions", json={"details": "dinner", **body})
        assert response.status_code == 422
    assert llm.calls == []


def test_suggestions_without_api_key_is_503(client, basics, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    response = client.post("/api/outfits/suggestions", json={"details": "dinner"})
    assert response.status_code == 503


def test_save_own_outfit(client, basics):
    b = basics
    response = client.post("/api/outfits", json={
        "aesthetic": "Sunday errands", "explanation": "comfy", "details": "",
        "garments": [{"garment_id": b["top"], "styling_advice": " tucked "}, {"garment_id": b["bottom"]}],
    })
    assert response.status_code == 201
    body = response.json()
    assert body["aesthetic"] == "Sunday errands"
    assert body["prompt_message"] == MANUAL_OUTFIT_REQUEST
    assert [(g["garment"]["id"], g["styling_advice"]) for g in body["garments"]] == [(b["top"], "tucked"), (b["bottom"], None)]


def test_save_own_outfit_uses_details_as_request(client, basics):
    response = client.post("/api/outfits", json={
        "aesthetic": "x", "explanation": "y", "details": "rainy day", "garments": [{"garment_id": basics["top"]}]})
    assert response.json()["prompt_message"] == "rainy day"


@pytest.mark.parametrize("change", [
    {"aesthetic": "  "},
    {"explanation": ""},
    {"garments": []},
    {"garments": [{"garment_id": 999}]},
    {"garments": "duplicate"},
])
def test_save_own_outfit_enforces_required_fields(client, basics, change):
    body = {"aesthetic": "x", "explanation": "y", "garments": [{"garment_id": basics["top"]}]}
    if change.get("garments") == "duplicate":
        change = {"garments": [{"garment_id": basics["top"]}, {"garment_id": basics["top"]}]}
    response = client.post("/api/outfits", json={**body, **change})
    assert response.status_code == 422
    assert client.get("/api/outfits").json() == []


# --- adding a garment from uploaded photos -------------------------------------------

def jpeg_bytes(size=(3000, 1500), color="navy"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "JPEG")
    return buffer.getvalue()


@pytest.fixture
def tagger(monkeypatch):
    """Replace the tagging LLM call; records the photo paths and context it got."""
    class Fake:
        calls = []
    def fake_tag(client, photo_paths, prompt_message=None, language="en-US", preferences=None):
        Fake.calls.append({"sizes": [Image.open(p).size for p in photo_paths], "prompt": prompt_message})
        return TaggingResult(garment=TEST_GARMENT, photos=[PhotoTag(index=i, role="front" if i == 0 else "label") for i in range(len(photo_paths))]), None
    monkeypatch.setattr(intake, "tag_garment", fake_tag)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return Fake


def upload(client, **data):
    files = [("photos", ("IMG_1.jpg", jpeg_bytes(), "image/jpeg")), ("photos", ("IMG_2.jpg", jpeg_bytes((800, 600)), "image/jpeg"))]
    response = client.post("/api/garments/drafts", files=files, data=data)
    assert response.status_code == 201
    return response.json()


def test_tagging_returns_a_draft_and_adds_nothing_yet(client, tagger):
    draft = upload(client, prompt_message="true color is navy", notes="  gift  ")
    assert draft["garment"]["notes"] == "gift"
    assert tagger.calls == [{"sizes": [(2000, 1000), (800, 600)], "prompt": "true color is navy"}]
    assert client.get("/api/garments").json() == []


def test_accepting_a_draft_saves_the_reviewed_values_and_files_the_photos(client, tagger):
    draft = upload(client)
    reviewed = {**draft["garment"], "fit": "oversized", "hem": "thigh"}

    response = client.post(f"/api/garments/drafts/{draft['id']}", json=reviewed)

    assert response.status_code == 201
    body = response.json()
    assert (body["fit"], body["hem"]) == ("oversized", "thigh")
    assert [p["role"] for p in body["photos"]] == ["front", "label"]
    # the /photos mount is bound to the real folder at startup, so check the filed photo via its thumbnail
    assert client.get(body["photos"][0]["thumb_url"]).status_code == 200
    assert [g["id"] for g in client.get("/api/garments").json()] == [body["id"]]


def test_a_draft_can_only_be_accepted_once(client, tagger):
    draft = upload(client)
    assert client.post(f"/api/garments/drafts/{draft['id']}", json=draft["garment"]).status_code == 201
    assert client.post(f"/api/garments/drafts/{draft['id']}", json=draft["garment"]).status_code == 404
    assert len(client.get("/api/garments").json()) == 1


def test_accepting_rejects_an_invalid_value_and_keeps_the_draft(client, tagger):
    draft = upload(client)
    bad = client.post(f"/api/garments/drafts/{draft['id']}", json={**draft["garment"], "fit": "enormous"})
    assert bad.status_code == 422
    assert client.post(f"/api/garments/drafts/{draft['id']}", json=draft["garment"]).status_code == 201


def test_accepting_ignores_ids_and_dates_sent_by_the_page(client, tagger):
    draft = upload(client)
    sneaky = {**draft["garment"], "id": 99, "user_id": 7, "set_id": 5, "disowned_on": "2026-01-01", "mended_on": "2026-01-01"}
    body = client.post(f"/api/garments/drafts/{draft['id']}", json=sneaky).json()
    assert body["id"] != 99
    assert body["set_id"] is None and body["disowned_on"] is None and body["mended_on"] is None


def test_discarding_a_draft_deletes_it(client, tagger, tmp_path):
    draft = upload(client)
    assert client.delete(f"/api/garments/drafts/{draft['id']}").status_code == 204
    assert not list((tmp_path / "intake" / "drafts" / "1").iterdir())
    assert client.post(f"/api/garments/drafts/{draft['id']}", json=draft["garment"]).status_code == 404
    assert client.get("/api/garments").json() == []


def test_discarding_twice_is_harmless(client, tagger):
    draft = upload(client)
    assert client.delete(f"/api/garments/drafts/{draft['id']}").status_code == 204
    assert client.delete(f"/api/garments/drafts/{draft['id']}").status_code == 204


def test_a_discarded_drafts_tokens_still_count(client, tagger, tmp_path, monkeypatch):
    def fake_tag(client, photo_paths, prompt_message=None, language="en-US", preferences=None):
        usage = TokenUsage(model="m", input_tokens=10, output_tokens=5)
        return TaggingResult(garment=TEST_GARMENT, photos=[PhotoTag(index=i, role="front") for i in range(len(photo_paths))]), usage
    monkeypatch.setattr(intake, "tag_garment", fake_tag)

    draft = upload(client)
    client.delete(f"/api/garments/drafts/{draft['id']}")

    [line] = (tmp_path / "tagging_log.jsonl").read_text().splitlines()
    assert json.loads(line)["usage"]["input_tokens"] == 10


def test_a_refused_tagging_call_is_logged_with_its_request_id(client, tagger, tmp_path, monkeypatch):
    """2026-11-08: the API refused tagging ("Schema is too complex") and the only trace was in docker logs."""
    import anthropic, httpx
    def refusing_tag(client, photo_paths, prompt_message=None, language="en-US", preferences=None):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        response = httpx.Response(400, request=request, headers={"request-id": "req_123"})
        raise anthropic.BadRequestError("Schema is too complex.", response=response, body=None)
    monkeypatch.setattr(intake, "tag_garment", refusing_tag)

    response = client.post("/api/garments/drafts", files=[("photos", ("a.jpg", jpeg_bytes(), "image/jpeg"))])

    assert response.status_code == 502
    [line] = [json.loads(line) for line in (tmp_path / "tagging_log.jsonl").read_text().splitlines()]
    assert line["usage"] is None   # nothing was billed, so the usage page shows nothing
    assert "Schema is too complex" in line["error"]
    assert line["request_id"] == "req_123"


def test_an_accepted_draft_counts_its_tokens_once(client, tagger, tmp_path, monkeypatch):
    def fake_tag(client, photo_paths, prompt_message=None, language="en-US", preferences=None):
        usage = TokenUsage(model="m", input_tokens=10, output_tokens=5)
        return TaggingResult(garment=TEST_GARMENT, photos=[PhotoTag(index=i, role="front") for i in range(len(photo_paths))]), usage
    monkeypatch.setattr(intake, "tag_garment", fake_tag)

    draft = upload(client)
    client.post(f"/api/garments/drafts/{draft['id']}", json=draft["garment"])

    lines = [json.loads(line) for line in (tmp_path / "tagging_log.jsonl").read_text().splitlines()]
    assert [bool(line["usage"]) for line in lines] == [True, False]
    assert lines[1]["draft_id"] == draft["id"]


@pytest.mark.parametrize("draft_id", ["../../etc", "nothex", "0" * 31])
def test_malformed_draft_ids_find_nothing(client, tagger, draft_id):
    assert client.post(f"/api/garments/drafts/{draft_id}", json=TEST_GARMENT.model_dump(mode="json")).status_code in (404, 405)


def test_upload_rejects_non_images(client, tagger):
    response = client.post("/api/garments/drafts", files=[("photos", ("notes.txt", b"not a photo", "text/plain"))])
    assert response.status_code == 422
    assert "notes.txt" in response.json()["detail"]
    assert tagger.calls == []


def test_upload_needs_a_photo(client, tagger):
    assert client.post("/api/garments/drafts", data={"notes": "x"}).status_code == 422


# --- thumbnails ----------------------------------------------------------------------

def test_thumbnail_is_small_and_cached(client, db_path, tmp_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    folder = tmp_path / "garments" / str(garment_id)
    folder.mkdir(parents=True)
    Image.new("RGB", (3000, 4000), "white").save(folder / "front_00.jpg")

    photo = client.get(f"/api/garments/{garment_id}").json()["photos"][0]
    assert photo["thumb_url"] == f"/thumbs/{garment_id}/front_00.jpg"
    response = client.get(photo["thumb_url"])
    assert response.status_code == 200
    assert Image.open(io.BytesIO(response.content)).size == (600, 800)
    cached = tmp_path / "thumbs" / str(garment_id) / "front_00.jpg.jpg"
    assert cached.is_file()


@pytest.mark.parametrize("path", ["/thumbs/1/missing.jpg", "/thumbs/1/..%2F..%2Ftest.db", "/thumbs/abc/front_00.jpg"])
def test_thumbnail_bad_requests(client, path):
    assert client.get(path).status_code in (404, 422)


# --- style preferences ---------------------------------------------------------------

def test_preferences_start_empty(client):
    assert client.get("/api/preferences").json() == {"text": None, "updated_at": None}


def test_preferences_save_replace_and_clear(client):
    first = client.put("/api/preferences", json={"text": "  loose fits  "}).json()
    assert first["text"] == "loose fits" and first["updated_at"]
    assert client.put("/api/preferences", json={"text": "glasses with every outfit"}).json()["text"] == "glasses with every outfit"
    assert client.put("/api/preferences", json={"text": "   "}).json() == {"text": None, "updated_at": None}


def test_preferences_length_is_capped(client):
    assert client.put("/api/preferences", json={"text": "x" * 4001}).status_code == 422


def test_improve_returns_rewrite_without_saving(client, monkeypatch, tmp_path):
    from enclothed.models import TokenUsage
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    seen = {}
    def fake_improve(client_, text):
        seen["text"] = text
        return "Needs:\n- glasses in every outfit", TokenUsage(model="m", input_tokens=10, output_tokens=5)
    monkeypatch.setattr(api, "improve_preferences", fake_improve)
    response = client.post("/api/preferences/improve", json={"text": "i need my glasses"})
    assert response.status_code == 200
    assert response.json() == {"text": "Needs:\n- glasses in every outfit"}
    assert seen == {"text": "i need my glasses"}
    assert client.get("/api/preferences").json()["text"] is None
    assert (tmp_path / "preferences_log.jsonl").read_text().count("\n") == 1


def test_improve_needs_text(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert client.post("/api/preferences/improve", json={"text": "  "}).status_code == 422


def test_suggestions_include_saved_preferences(client, basics, llm):
    b = basics
    llm.result = OutfitResult.model_validate({"outfits": [suggestion([b["top"], b["bottom"], b["shoes"]])]})
    client.put("/api/preferences", json={"text": "always suggest glasses"})
    client.post("/api/outfits/suggestions", json={"details": "dinner"})
    texts = [block["text"] for block in llm.calls[-1]]
    assert any("<preferences>" in t and "always suggest glasses" in t for t in texts)


def test_suggestions_without_preferences_send_no_block(client, basics, llm):
    b = basics
    llm.result = OutfitResult.model_validate({"outfits": [suggestion([b["top"], b["bottom"], b["shoes"]])]})
    client.post("/api/outfits/suggestions", json={"details": "dinner"})
    assert not any("<preferences>" in block["text"] for block in llm.calls[-1])


# --- caching of the page's files ------------------------------------------------------
@pytest.mark.parametrize("path", ["/", "/static/js/main.js", "/static/css/app.css"])
def test_page_files_must_be_rechecked(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_unchanged_page_file_is_not_sent_again(client):
    first = client.get("/static/js/main.js")
    second = client.get("/static/js/main.js", headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 304


# --- disowning garments -----------------------------------------------------------------
def disown(client, garment_id, day="2026-11-03"):
    return client.patch(f"/api/garments/{garment_id}", json={"disowned_on": day})


def test_disown_through_patch(client, db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    response = disown(client, garment_id)
    assert response.status_code == 200
    assert response.json()["disowned_on"] == "2026-11-03"
    assert client.get(f"/api/garments/{garment_id}").json()["disowned_on"] == "2026-11-03"


def test_disown_rejects_a_bad_date(client, db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    assert disown(client, garment_id, "someday").status_code == 422
    assert client.get(f"/api/garments/{garment_id}").json()["disowned_on"] is None


def test_garment_list_keeps_disowned(client, db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    disown(client, garment_id)
    assert [g["id"] for g in client.get("/api/garments").json()] == [garment_id]


def test_outfit_with_a_disowned_piece_still_loads(client, outfit_id):
    piece = client.get(f"/api/outfits/{outfit_id}").json()["garments"][0]["garment"]["id"]
    disown(client, piece)
    assert client.get(f"/api/outfits/{outfit_id}").status_code == 200
    [listed] = client.get("/api/outfits").json()
    assert listed["wear_count"] == 0
    assert piece in [g["garment"]["id"] for g in listed["garments"]]


def test_disowned_anchor_is_rejected(client, db_path, monkeypatch):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    disown(client, garment_id)
    monkeypatch.setattr(api, "_anthropic_client", lambda: None)
    response = client.post("/api/outfits/suggestions", json={"anchors": [garment_id]})
    assert response.status_code == 422
    assert str(garment_id) in response.json()["detail"]


def test_saving_an_outfit_with_a_disowned_piece_is_rejected(client, db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    disown(client, garment_id)
    response = client.post("/api/outfits", json={"aesthetic": "a", "explanation": "b", "garments": [{"garment_id": garment_id}]})
    assert response.status_code == 422


def test_disowned_garment_is_not_sent_to_the_llm(client, db_path, monkeypatch):
    kept = insert_garment(db_path, 1, TEST_GARMENT)
    gone = insert_garment(db_path, 1, TEST_GARMENT)
    disown(client, gone)
    sent = {}

    def fake_recommend(_client, context, language="en-US"):
        sent["wardrobe"] = context[0]["text"]
        return OutfitResult(outfits=[]), None

    monkeypatch.setattr(api, "_anthropic_client", lambda: None)
    monkeypatch.setattr(outfit_module, "recommend_outfits", fake_recommend)
    assert client.post("/api/outfits/suggestions", json={"details": "dinner"}).status_code == 200

    wardrobe = json.loads(sent["wardrobe"].split("<wardrobe>")[1].split("</wardrobe>")[0])
    assert set(wardrobe) == {str(kept)}


def test_clearing_disowned_on_puts_a_garment_back(client, db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    disown(client, garment_id)
    response = client.patch(f"/api/garments/{garment_id}", json={"disowned_on": None})
    assert response.status_code == 200
    assert response.json()["disowned_on"] is None
    assert [g.id for g in select_owned_garments(db_path, 1)] == [garment_id]


# --- startup -----------------------------------------------------------------------------
def test_server_start_creates_the_db(tmp_path, monkeypatch, signed_in):
    path = tmp_path / "new.db"
    monkeypatch.setattr(api, "DB_PATH", path)
    assert not path.exists()
    with TestClient(api.app) as client:   # "with" runs the startup code
        assert client.get("/api/garments").json() == []


# --- describe: AI fills a blank name or explanation for your own outfit ---
from enclothed.llm import UnusableResponse, describe_system_prompt
from enclothed.models import OutfitDescription


@pytest.fixture
def describer(monkeypatch):
    """Replace the describe LLM call; records what it was sent and returns `describer.result`."""
    class Fake:
        result = OutfitDescription(aesthetic=" Quiet weekend ", explanation=" The navy and khaki stay calm. ")
        calls = []
        error = None
    def fake_describe(client, context, language="en-US"):
        Fake.calls.append({"context": "\n".join(block["text"] for block in context), "language": language})
        if Fake.error:
            raise Fake.error
        return Fake.result, TokenUsage(model="m", input_tokens=10, output_tokens=5)
    monkeypatch.setattr(outfit_module, "describe_outfit", fake_describe)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    Fake.calls = []
    return Fake


def test_describe_fills_both_blanks_and_saves_nothing(client, basics, describer, tmp_path):
    b = basics
    response = client.post("/api/outfits/describe", json={"garments": [b["top"], b["bottom"]], "details": "rainy Sunday"})
    assert response.status_code == 200
    assert response.json() == {"aesthetic": "Quiet weekend", "explanation": "The navy and khaki stay calm."}
    sent = describer.calls[0]["context"]
    assert "<outfit>" in sent and "rainy Sunday" in sent and "<given>" not in sent
    assert client.get("/api/outfits").json() == []
    entry = json.loads((tmp_path / "outfit_log.jsonl").read_text())
    assert entry["kind"] == "describe" and entry["usage"]["input_tokens"] == 10


def test_describe_keeps_what_the_user_wrote(client, basics, describer):
    b = basics
    describer.result = OutfitDescription(aesthetic="A different name", explanation="Why it works.")
    response = client.post("/api/outfits/describe", json={"garments": [b["top"]], "aesthetic": "Sunday errands"})
    assert response.json() == {"aesthetic": "Sunday errands", "explanation": "Why it works."}
    assert '"aesthetic": "Sunday errands"' in describer.calls[0]["context"]


def test_describe_with_both_written_skips_the_llm(client, basics, describer, tmp_path):
    response = client.post("/api/outfits/describe", json={"garments": [basics["top"]], "aesthetic": "Mine", "explanation": "Also mine."})
    assert response.json() == {"aesthetic": "Mine", "explanation": "Also mine."}
    assert describer.calls == []
    assert not (tmp_path / "outfit_log.jsonl").exists()


def test_describe_includes_preferences_and_language(client, basics, describer):
    client.put("/api/preferences", json={"text": "I like muted colors"})
    api.app.dependency_overrides[signed_in_user] = lambda: User(id=1, username="owner", is_admin=True, language="ja-JP")
    client.post("/api/outfits/describe", json={"garments": [basics["top"]]})
    assert "I like muted colors" in describer.calls[0]["context"]
    assert describer.calls[0]["language"] == "ja-JP"


def test_describe_rejects_unknown_or_missing_garments(client, basics, describer):
    assert client.post("/api/outfits/describe", json={"garments": [9999]}).status_code == 422
    assert client.post("/api/outfits/describe", json={"garments": []}).status_code == 422
    assert describer.calls == []


def test_describe_unusable_answer_is_502_and_still_logged(client, basics, describer, tmp_path):
    describer.error = UnusableResponse("No description", TokenUsage(model="m", input_tokens=7, output_tokens=0))
    response = client.post("/api/outfits/describe", json={"garments": [basics["top"]]})
    assert response.status_code == 502
    assert json.loads((tmp_path / "outfit_log.jsonl").read_text())["usage"]["input_tokens"] == 7


def test_describe_blank_answer_counts_as_unusable(client, basics, describer):
    describer.result = OutfitDescription(aesthetic="  ", explanation="Fine.")
    assert client.post("/api/outfits/describe", json={"garments": [basics["top"]]}).status_code == 502


def test_describe_prompt_names_the_language():
    assert "Japanese" in describe_system_prompt("ja-JP")
    assert "Language:" not in describe_system_prompt("en-US")

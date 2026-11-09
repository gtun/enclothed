# tests/test_weigh.py
# weigh (#2): the shortlist, the placeholder ID swap, saving a candidate, and keeping candidates
# out of everything that means "my wardrobe". The LLM call is replaced; no tokens are spent.
import io
import json
import sqlite3
from contextlib import closing
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from enclothed import api, config, db, intake, photos, sandbox
from enclothed import weigh as weigh_module
from enclothed.auth import signed_in_user
from enclothed.config import MIGRATIONS_DIR, SCHEMA_PATH
from enclothed.intake import TEST_GARMENT
from enclothed.llm import UnusableResponse
from enclothed.models import Outfit, OutfitGarment, PhotoTag, TaggingResult, TokenUsage, User, WeighResult
from enclothed.weigh import CANDIDATE_ID, check_similar, similar_garments, similar_score, weigh_context, with_real_id

USAGE = TokenUsage(model="m", input_tokens=10, output_tokens=5)


def garment(**changes):
    return TEST_GARMENT.model_copy(update=changes)


# --- the shortlist ------------------------------------------------------------------------

def test_same_subcategory_and_color_rank_first():
    candidate = garment(category="top", subcategory="t-shirt", primary_color="white", formality=1)
    owned = {
        1: garment(id=1, category="top", subcategory="oxford shirt", primary_color="white", formality=2),
        2: garment(id=2, category="top", subcategory="t-shirt", primary_color="white", formality=1),
        3: garment(id=3, category="top", subcategory="t-shirt", primary_color="black", formality=1),
        4: garment(id=4, category="bottom", subcategory="jeans", primary_color="white"),
    }
    assert similar_garments(candidate, owned) == [2, 3, 1]   # the jeans are another category


def test_ties_keep_the_lower_id_first_and_the_limit_holds():
    candidate = garment(category="top", subcategory="t-shirt")
    owned = {i: garment(id=i, category="top", subcategory="t-shirt") for i in (9, 3, 5)}
    assert similar_garments(candidate, owned, limit=2) == [3, 5]


def test_a_secondary_color_match_counts_less_than_a_primary_one():
    candidate = garment(primary_color="navy", secondary_colors=[], fabric_type=None, pattern=None, fit=None)
    primary = garment(primary_color="navy", secondary_colors=[], fabric_type=None, pattern=None, fit=None)
    secondary = garment(primary_color="white", secondary_colors=["navy"], fabric_type=None, pattern=None, fit=None)
    assert similar_score(candidate, primary) == similar_score(candidate, secondary) + 1


def test_nothing_in_the_category_gives_an_empty_shortlist_and_says_so():
    candidate = garment(category="shoes", subcategory="loafers")
    owned = {1: garment(id=1)}
    assert similar_garments(candidate, owned) == []
    context = weigh_context(owned, candidate, [], None, {"safe": 1, "stretch": 1, "bold": 1})
    assert any("(nothing owned in this category)" in block["text"] for block in context)


# --- the message --------------------------------------------------------------------------

def test_the_wardrobe_is_first_and_cached_and_has_no_candidate():
    owned = {1: garment(id=1), 2: garment(id=2)}
    context = weigh_context(owned, garment(id=CANDIDATE_ID), [1], "likes black", {"safe": 1, "stretch": 1, "bold": 1})
    assert context[0]["cache_control"] == {"type": "ephemeral"}
    wardrobe = json.loads(context[0]["text"].split("\n")[1])
    assert set(wardrobe) == {"1", "2"}
    texts = [block["text"] for block in context]
    assert [t.split(">")[0] + ">" for t in texts[1:]] == ["<preferences>", "<candidate>", "<similar>", "<anchors>", "<options>", "<weigh>"]
    assert texts[4] == f"<anchors>\n{CANDIDATE_ID}: {garment().name}\n</anchors>"


# --- checking and fixing up the reply -----------------------------------------------------

def result(outfit_ids=((CANDIDATE_ID, 1, 2, 3),), similar=(1,), tiers=("safe", "stretch", "bold")):
    check = {"answer": True, "reason": "because"}
    return WeighResult.model_validate({
        "already_own": {"answer": False, "reason": "nothing like it"},
        "similar": [{"garment_id": i, "similarity": "close", "differences": "color"} for i in similar],
        "outfits": [{"aesthetic": f"look {n}", "explanation": "why", "risk_tier": tiers[n % 3],
                     "garments": [{"garment_id": i, "styling_advice": None} for i in ids]} for n, ids in enumerate(outfit_ids)],
        "makes_outfits": check, "fills_gap": check, "fits_style": check,
        "recommendation": "maybe", "summary": "It's fine.",
    })


def test_similar_matches_outside_the_shortlist_are_dropped():
    problems, kept = check_similar(result(similar=(1, 7)), [1, 2])
    assert [m.garment_id for m in kept.similar] == [1]
    assert problems == ["similar: dropped garment id(s) not in <similar>: [7]"]


def test_with_real_id_swaps_only_the_placeholder_and_leaves_the_input_alone():
    outfit = Outfit(aesthetic="a", explanation="e", garments=[OutfitGarment(garment_id=CANDIDATE_ID), OutfitGarment(garment_id=4)])
    swapped = with_real_id(outfit, 42)
    assert [g.garment_id for g in swapped.garments] == [42, 4]
    assert outfit.garments[0].garment_id == CANDIDATE_ID


def test_verdict_is_everything_but_the_outfits():
    verdict = result().verdict()
    assert verdict.recommendation == "maybe"
    assert "outfits" not in verdict.model_dump()


# --- the API, end to end ------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(api, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(api, "THUMBS_DIR", tmp_path / "thumbs")
    monkeypatch.setattr(api, "INTAKE_DIR", tmp_path / "intake")
    monkeypatch.setattr(api, "TAGGING_LOG_PATH", tmp_path / "tagging_log.jsonl")
    monkeypatch.setattr(api, "WEIGH_LOG_PATH", tmp_path / "weigh_log.jsonl")
    monkeypatch.setattr(photos, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(photos, "THUMBS_DIR", tmp_path / "thumbs")
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    api.app.dependency_overrides[signed_in_user] = lambda: User(id=1, username="owner", is_admin=True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(intake, "tag_garment", lambda client, paths, *a, **kw: (
        TaggingResult(garment=garment(category="top", subcategory="t-shirt"), photos=[PhotoTag(index=i, role="front") for i in range(len(paths))]), USAGE))
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


@pytest.fixture
def owned(db_path):
    """A top, a bottom and shoes the user owns."""
    make = lambda **kw: db.insert_garment(db_path, 1, garment(**kw))
    return [make(category="top", subcategory="t-shirt"), make(category="bottom", subcategory="jeans"), make(category="shoes", subcategory="loafers")]


@pytest.fixture
def llm(monkeypatch):
    """Replace the weigh call; set .reply (a WeighResult or an exception) and read .calls."""
    class Fake:
        reply = None
        calls = []
    def fake(client, context, language="en-US"):
        Fake.calls.append(context)
        if isinstance(Fake.reply, Exception):
            raise Fake.reply
        return Fake.reply, USAGE
    Fake.calls = []
    monkeypatch.setattr(weigh_module, "weigh_candidate", fake)
    return Fake


def jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "navy").save(buffer, "JPEG")
    return buffer.getvalue()


def new_draft(client):
    response = client.post("/api/garments/drafts", files=[("photos", ("a.jpg", jpeg(), "image/jpeg"))])
    assert response.status_code == 201
    return response.json()


def weigh(client, draft):
    return client.post("/api/weighs", json={"draft_id": draft["id"], "garment": draft["garment"]})


def test_weighing_saves_a_candidate_with_its_verdict_and_outfits(client, db_path, owned, llm):
    top, bottom, shoes = owned
    llm.reply = result(outfit_ids=[(CANDIDATE_ID, bottom, shoes)] * 3, similar=[top])
    response = weigh(client, new_draft(client))
    assert response.status_code == 201
    body = response.json()

    candidate = body["candidate"]
    assert candidate["weighed_on"] is not None
    assert candidate["photos"]            # filed under the new garment, like an added one
    assert body["weigh"]["garment_id"] == candidate["id"]
    assert body["weigh"]["verdict"]["similar"][0]["garment_id"] == top
    assert len(body["outfits"]) == 3
    first = body["outfits"][0]["garments"]
    assert {(g["garment"]["id"], g["is_anchor"]) for g in first} == {(candidate["id"], True), (bottom, False), (shoes, False)}
    assert body["outfits"][0]["prompt_message"].startswith("Weighing: ")

    assert client.get("/api/weighs").json() == [body["weigh"]]
    assert candidate["id"] not in {g.id for g in db.select_owned_garments(db_path, 1)}


def test_the_call_sees_owned_garments_but_not_other_candidates(client, owned, llm):
    llm.reply = result(outfit_ids=[(CANDIDATE_ID, owned[1], owned[2])] * 3, similar=[owned[0]])
    first = weigh(client, new_draft(client)).json()["candidate"]["id"]
    weigh(client, new_draft(client))
    wardrobe = json.loads(llm.calls[1][0]["text"].split("\n")[1])
    assert str(first) not in wardrobe
    assert set(wardrobe) == {str(i) for i in owned}


def test_a_failed_call_saves_nothing_and_keeps_the_draft_for_a_retry(client, db_path, owned, llm):
    draft = new_draft(client)
    llm.reply = UnusableResponse("no verdict", USAGE)
    assert weigh(client, draft).status_code == 502
    assert db.select_all_garments(db_path, 1) == db.select_owned_garments(db_path, 1)   # no candidate
    llm.reply = result(outfit_ids=[(CANDIDATE_ID, owned[1], owned[2])] * 3, similar=[owned[0]])
    assert weigh(client, draft).status_code == 201   # same draft, no second tagging call


def test_a_draft_that_is_gone_fails_before_the_call(client, llm):
    response = client.post("/api/weighs", json={"draft_id": "0" * 32, "garment": garment().model_dump(mode="json")})
    assert response.status_code == 404
    assert llm.calls == []


def test_invalid_outfits_are_dropped_but_the_verdict_is_kept(client, owned, llm):
    llm.reply = result(outfit_ids=[(CANDIDATE_ID, owned[1], owned[2]), (owned[1], owned[2]), (CANDIDATE_ID, 999)], similar=[owned[0]])
    body = weigh(client, new_draft(client)).json()
    assert len(body["outfits"]) == 1          # one lacks the candidate, one has an unknown garment
    assert body["weigh"]["verdict"]["summary"] == "It's fine."


def test_buying_makes_it_owned_and_its_outfits_ordinary(client, db_path, owned, llm):
    llm.reply = result(outfit_ids=[(CANDIDATE_ID, owned[1], owned[2])] * 3, similar=[owned[0]])
    candidate = weigh(client, new_draft(client)).json()["candidate"]["id"]
    response = client.post(f"/api/weighs/{candidate}/buy")
    assert response.status_code == 200
    assert response.json()["weighed_on"] is None
    assert candidate in {g.id for g in db.select_owned_garments(db_path, 1)}
    assert client.get("/api/weighs").json() == []
    assert client.post(f"/api/weighs/{candidate}/buy").status_code == 404   # already owned


def test_not_buying_deletes_the_candidate_its_outfits_and_photos(client, db_path, owned, llm, tmp_path):
    llm.reply = result(outfit_ids=[(CANDIDATE_ID, owned[1], owned[2])] * 3, similar=[owned[0]])
    body = weigh(client, new_draft(client)).json()
    candidate = body["candidate"]["id"]
    assert (tmp_path / "garments" / str(candidate)).is_dir()

    assert client.delete(f"/api/weighs/{candidate}").status_code == 204
    assert db.select_garment(db_path, 1, candidate) is None
    assert client.get("/api/outfits").json() == []
    assert client.get("/api/weighs").json() == []
    assert not (tmp_path / "garments" / str(candidate)).exists()
    assert client.delete(f"/api/weighs/{candidate}").status_code == 404


def test_an_owned_garment_can_never_be_deleted_as_a_candidate(client, db_path, owned):
    assert client.delete(f"/api/weighs/{owned[0]}").status_code == 404
    assert db.select_garment(db_path, 1, owned[0]) is not None


def test_weighed_on_cant_be_changed_by_patch(client, owned):
    response = client.patch(f"/api/garments/{owned[0]}", json={"weighed_on": "2026-11-08"})
    assert response.status_code == 422


def test_the_call_is_logged_for_usage(client, owned, llm, tmp_path):
    llm.reply = result(outfit_ids=[(CANDIDATE_ID, owned[1], owned[2])] * 3, similar=[owned[0]])
    weigh(client, new_draft(client))
    kinds = [c["kind"] for c in client.get("/api/usage").json()]
    assert kinds.count("weigh") == 1


# --- candidates stay out of "my wardrobe" -------------------------------------------------

def test_insights_never_sees_candidates_or_their_outfits(db_path):
    mine = db.insert_garment(db_path, 1, garment())
    maybe = db.insert_garment(db_path, 1, garment(weighed_on=date(2026, 11, 8)))
    ordinary = Outfit(aesthetic="mine", explanation="e", garments=[OutfitGarment(garment_id=mine)])
    with_candidate = Outfit(aesthetic="maybe", explanation="e", garments=[OutfitGarment(garment_id=mine), OutfitGarment(garment_id=maybe)])
    db.insert_outfits(db_path, 1, [ordinary, with_candidate], None, "x", "2026-11-08T00:00:00+00:00")
    with closing(sandbox.build_snapshot(db_path, 1)) as conn:
        assert [r[0] for r in conn.execute("SELECT id FROM garments")] == [mine]
        assert [r[0] for r in conn.execute("SELECT aesthetic FROM outfits")] == ["mine"]
        assert conn.execute("SELECT COUNT(*) FROM outfit_garments").fetchone()[0] == 1


def test_resetting_the_demo_clears_its_weighs(db_path):
    demo_id = db.insert_demo_user(db_path, "demo")
    maybe = db.insert_garment(db_path, demo_id, garment(weighed_on=date(2026, 11, 8)))
    db.insert_weigh(db_path, demo_id, maybe, result().verdict(), "2026-11-08T00:00:00+00:00")
    assert db.delete_demo_wardrobe(db_path, demo_id, keep=set()) == [maybe]
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM weighs").fetchone()[0] == 0

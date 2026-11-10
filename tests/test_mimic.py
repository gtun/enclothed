# tests/test_mimic.py
# mimic (#5): reading a look into pieces, the shortlists, checking the matches, saving a look and its
# recreations, and the API around it. Both LLM calls are replaced; no tokens are spent.
import io
import json
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from enclothed import api, db, llm, mimic, photos
from enclothed.auth import signed_in_user
from enclothed.cli_display import format_look
from enclothed.config import MIGRATIONS_DIR, SCHEMA_PATH
from enclothed.intake import TEST_GARMENT
from enclothed.llm import UnusableResponse
from enclothed.models import LookPiece, LookReply, LookTags, MimicResult, TokenUsage, User, to_look_tags

USAGE = TokenUsage(model="m", input_tokens=10, output_tokens=5)


def garment(**changes):
    return TEST_GARMENT.model_copy(update=changes)


def piece(**changes):
    fields = {"category": "top", "subcategory": "t-shirt", "primary_color": "white", "description": "A white tee.", "role": "the base"}
    return LookPiece(**{**fields, **changes})


LOOK = LookTags(title="Easy navy", summary="Navy over white.", silhouette="H", pieces=[
    piece(category="outerwear", subcategory="chore coat", primary_color="navy", description="A boxy navy chore coat, worn open", role="structure"),
    piece(),
    piece(category="bottom", subcategory="jeans", primary_color="indigo", description="Straight indigo jeans.", role="the line below"),
    piece(category="accessory", subcategory="tote bag", primary_color="cream", description="A canvas tote.", role="texture", essential=False),
])


def recreation(matches, garments, aesthetic="Navy recreation"):
    return {"matches": [{"piece": p, "garment_id": g, "closeness": c, "note": n} for p, g, c, n in matches],
            "garments": [{"garment_id": i, "styling_advice": None} for i in garments],
            "aesthetic": aesthetic, "explanation": "Close to the look."}


# --- reading the tagging reply ------------------------------------------------------------

def tagged_piece(**changes):
    fields = {"category": "top", "subcategory": "t-shirt", "primary_color": "white", "secondary_colors": [], "pattern": "",
              "formality": 0, "warmth": 0, "fit": "unknown", "sheen": "unknown", "fabric_type": "unknown", "shape": "unknown",
              "hem": "unknown", "fabric_weight": "unknown", "sleeve": "unknown", "statement": "unknown",
              "description": "A tee.", "role": "base", "essential": True}
    return {**fields, **changes}


def test_unknowns_become_blank_and_the_silhouette_can_be_none():
    reply = LookReply.model_validate({"title": " Easy ", "summary": "s", "silhouette": "unknown",
                                      "pieces": [tagged_piece(fit="relaxed", formality=2)]})
    tags = to_look_tags(reply)
    assert tags.title == "Easy"
    assert tags.silhouette is None
    [p] = tags.pieces
    assert (p.fit, p.formality, p.sheen, p.pattern, p.warmth) == ("relaxed", 2, None, None, None)


def test_an_odd_subcategory_or_fabric_becomes_other_rather_than_losing_the_call():
    reply = LookReply.model_validate({"title": "t", "summary": "s", "silhouette": "A",
                                      "pieces": [tagged_piece(subcategory="space suit", fabric_type="moonweave")]})
    [p] = to_look_tags(reply).pieces
    assert (p.subcategory, p.fabric_type) == ("other", "other")


def test_a_piece_reads_as_a_garment_for_the_shortlist():
    g = piece(fit="slim", description="Slim and white.").as_garment()
    assert (g.category, g.subcategory, g.fit, g.styling_notes) == ("top", "t-shirt", "slim", "Slim and white.")


# --- shortlists and the message -----------------------------------------------------------

@pytest.fixture
def owned():
    return {
        1: garment(id=1, category="outerwear", subcategory="chore coat", primary_color="navy"),
        2: garment(id=2, category="top", subcategory="t-shirt", primary_color="white"),
        3: garment(id=3, category="bottom", subcategory="jeans", primary_color="indigo"),
        4: garment(id=4, category="shoes", subcategory="loafers", primary_color="brown"),
        5: garment(id=5, category="top", subcategory="t-shirt", primary_color="black"),
    }


def test_each_piece_gets_its_own_shortlist_by_number(owned):
    lists = mimic.shortlists(LOOK.pieces, owned)
    assert lists == {1: [1], 2: [2, 5], 3: [3], 4: []}


def test_the_wardrobe_is_first_and_cached_and_the_pieces_are_numbered_from_one(owned):
    context = mimic.mimic_context(owned, LOOK, mimic.shortlists(LOOK.pieces, owned), "the coat matters most", "likes navy")
    assert context[0]["cache_control"] == {"type": "ephemeral"}
    texts = [block["text"] for block in context]
    assert [t.split(">")[0] + ">" for t in texts[1:]] == ["<preferences>", "<look>", "<note>", "<shortlists>", "<mimic>"]
    look = json.loads(texts[2].split("\n")[1])
    assert look["silhouette"] == "H-line"
    assert list(look["pieces"]) == ["1", "2", "3", "4"]
    assert look["pieces"]["1"]["layer"] == "outer"
    assert "4 (cream tote bag): (nothing owned in this category)" in texts[4]


def test_mimic_shares_the_outfit_system_prompt_so_the_wardrobe_cache_is_shared():
    # The cache covers the system prompt and the wardrobe block; mimic sends its own rules in the message.
    assert "<mimic>" not in llm.OUTFIT_SYSTEM_PROMPT
    assert llm.MIMIC_INSTRUCTIONS.startswith("<mimic>")


# --- checking the matches -----------------------------------------------------------------

def test_good_matches_are_kept_in_piece_order(owned):
    result = MimicResult.model_validate({"outfits": [recreation(
        [(2, 2, "exact", ""), (1, 1, "close", "less boxy"), (3, 3, "close", "darker"), (4, 0, "none", "no tote")], [1, 2, 3, 4])]})
    problems, [(outfit, matches)] = mimic.check_recreations(result, LOOK.pieces, owned)
    assert problems == []
    assert [(m.piece, m.garment_id, m.closeness, m.note) for m in matches] == [
        (1, 1, "close", "less boxy"), (2, 2, "exact", None), (3, 3, "close", "darker"), (4, None, "none", "no tote")]
    assert outfit.missing == "A canvas tote."
    assert [g.garment_id for g in outfit.garments] == [1, 2, 3, 4]   # the loafers: added, though the photos showed no shoes


def test_bad_matches_become_none_instead_of_dropping_the_outfit(owned):
    result = MimicResult.model_validate({"outfits": [recreation(
        [(1, 5, "loose", ""),           # 5 isn't in the outfit
         (2, 2, "exact", ""), (3, 2, "loose", ""),   # 2 already stands in for piece 2
         (2, 2, "close", ""),           # piece 2 again
         (9, 3, "close", "")],          # there's no piece 9; piece 4 isn't answered at all
        [1, 2, 3, 4])]})
    problems, [(outfit, matches)] = mimic.check_recreations(result, LOOK.pieces, owned)
    assert [(m.piece, m.garment_id, m.closeness) for m in matches] == [(1, None, "none"), (2, 2, "exact"), (3, None, "none"), (4, None, "none")]
    assert len(problems) == 5
    assert outfit.missing == "A boxy navy chore coat, worn open. Straight indigo jeans. A canvas tote."


def test_an_outfit_that_breaks_the_outfit_rules_is_dropped_and_only_two_are_kept(owned):
    no_shoes = recreation([(2, 2, "exact", "")], [2, 3])
    good = recreation([(2, 2, "exact", "")], [2, 3, 4])
    result = MimicResult.model_validate({"outfits": [no_shoes, good, good, good]})
    problems, kept = mimic.check_recreations(result, LOOK.pieces, owned)
    assert len(kept) == 1     # the first had no shoes; the third and fourth were past the limit of two
    assert problems[0] == "4 recreations returned; kept the first 2"
    assert any("no footwear" in p for p in problems)


# --- the CLI's output ---------------------------------------------------------------------

def test_the_cli_shows_each_piece_its_stand_in_and_what_was_added(owned):
    result = MimicResult.model_validate({"outfits": [recreation([(1, 1, "close", "less boxy"), (2, 2, "exact", ""), (3, 3, "loose", ""), (4, 0, "none", "")], [1, 2, 3, 4])]})
    _, kept = mimic.check_recreations(result, LOOK.pieces, owned)
    text = format_look(LOOK, kept, owned)
    assert "LOOK: EASY NAVY [H-line]" in text
    assert "-> close" in text and "less boxy" in text
    assert "4. cream tote bag (texture)\n       -> nothing owned" in text
    assert "(not in the photos)" in text           # the loafers
    assert "To finish the look: A canvas tote." in text


def test_offline_mode_matches_the_top_of_each_shortlist(owned):
    [outfit] = mimic.offline_result(LOOK, owned).outfits
    assert [(m.garment_id, m.closeness) for m in outfit.matches] == [(1, "loose"), (2, "loose"), (3, "loose"), (0, "none")]
    assert [g.garment_id for g in outfit.garments] == [1, 2, 3]


# --- the API, end to end ------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(api, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(api, "INTAKE_DIR", tmp_path / "intake")
    monkeypatch.setattr(photos, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(photos, "THUMBS_DIR", tmp_path / "thumbs")
    monkeypatch.setattr(photos, "LOOKS_DIR", tmp_path / "looks")
    return path


@pytest.fixture
def wardrobe(db_path):
    make = lambda **kw: db.insert_garment(db_path, 1, garment(**kw))
    return [make(category="outerwear", subcategory="chore coat", primary_color="navy"), make(category="top", subcategory="t-shirt", primary_color="white"),
            make(category="bottom", subcategory="jeans", primary_color="indigo"), make(category="shoes", subcategory="loafers", primary_color="brown")]


@pytest.fixture
def llm_calls(monkeypatch):
    """Replace both calls. Set .tags / .match (a value or an exception) and read .match_contexts."""
    class Fake:
        tags = LOOK
        match = None
        tag_photos = []
        match_contexts = []
    def fake_tag(client, paths, note=None, language="en-US"):
        Fake.tag_photos.append(list(paths))
        if isinstance(Fake.tags, Exception):
            raise Fake.tags
        return Fake.tags, USAGE
    def fake_match(client, context, language="en-US"):
        Fake.match_contexts.append(context)
        if isinstance(Fake.match, Exception):
            raise Fake.match
        return Fake.match, USAGE
    Fake.tag_photos, Fake.match_contexts = [], []
    monkeypatch.setattr(mimic, "tag_look", fake_tag)
    monkeypatch.setattr(mimic, "match_look", fake_match)
    return Fake


@pytest.fixture
def client(db_path, monkeypatch):
    api.app.dependency_overrides[signed_in_user] = lambda: User(id=1, username="owner", is_admin=True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "navy").save(buffer, "JPEG")
    return buffer.getvalue()


def post_look(client, n=2, note=None):
    data = {"note": note} if note else {}
    return client.post("/api/looks", files=[("photos", (f"{i}.jpg", jpeg(), "image/jpeg")) for i in range(n)], data=data)


def recreate(client, look_id):
    return client.post(f"/api/looks/{look_id}/recreations")


def two_recreations(wardrobe):
    coat, tee, jeans, shoes = wardrobe
    first = recreation([(1, coat, "close", "less boxy"), (2, tee, "exact", ""), (3, jeans, "close", ""), (4, 0, "none", "")], [coat, tee, jeans, shoes], "Closest")
    second = recreation([(1, 0, "none", ""), (2, tee, "exact", ""), (3, jeans, "close", ""), (4, 0, "none", "")], [tee, jeans, shoes], "Without the coat")
    return MimicResult.model_validate({"outfits": [first, second]})


def test_a_look_is_saved_with_its_photos_then_recreated(client, db_path, wardrobe, llm_calls, tmp_path):
    response = post_look(client, note="the coat matters most")
    assert response.status_code == 201
    look = response.json()
    assert look["title"] == "Easy navy" and look["note"] == "the coat matters most"
    assert len(look["pieces"]) == 4
    assert look["recreations"] == []
    assert [p["url"] for p in look["photos"]] == [f"/looks/{look['id']}/00.jpg", f"/looks/{look['id']}/01.jpg"]
    assert (tmp_path / "looks" / str(look["id"]) / "01.jpg").is_file()
    assert llm_calls.match_contexts == []          # matching is its own request

    llm_calls.match = two_recreations(wardrobe)
    response = recreate(client, look["id"])
    assert response.status_code == 201
    body = response.json()
    outfits = body["outfits"]
    assert [o["aesthetic"] for o in outfits] == ["Closest", "Without the coat"]
    assert all(o["prompt_message"] == "Mimicking: Easy navy" and o["source"] == "ai" for o in outfits)
    assert outfits[0]["missing"] == "A canvas tote."
    look = body["look"]
    assert [r["outfit_id"] for r in look["recreations"]] == [o["id"] for o in outfits]
    assert look["recreations"][0]["matches"][0] == {"piece": 1, "garment_id": wardrobe[0], "closeness": "close", "note": "less boxy"}

    assert client.get("/api/looks").json() == [look]
    assert {o["id"] for o in client.get("/api/outfits").json()} == {o["id"] for o in outfits}
    assert client.get(look["photos"][0]["url"]).status_code == 200
    assert client.get(look["photos"][0]["thumb_url"]).status_code == 200
    assert recreate(client, look["id"]).status_code == 409     # one set of recreations per look


def test_the_photos_go_to_tagging_only_and_the_note_reaches_both_calls(client, wardrobe, llm_calls):
    llm_calls.match = two_recreations(wardrobe)
    look_id = post_look(client, n=3, note="ignore the bag").json()["id"]
    recreate(client, look_id)
    assert len(llm_calls.tag_photos[0]) == 3
    [context] = llm_calls.match_contexts
    assert all(block["type"] == "text" for block in context)       # no images in the matching call
    assert any("ignore the bag" in block["text"] for block in context)


def test_a_failed_match_saves_nothing_and_can_be_tried_again(client, db_path, wardrobe, llm_calls):
    look_id = post_look(client).json()["id"]
    llm_calls.match = UnusableResponse("no recreation", USAGE)
    response = recreate(client, look_id)
    assert response.status_code == 502
    assert response.json()["detail"] == api.MATCH_FAILED
    assert client.get("/api/looks").json()[0]["recreations"] == []
    assert client.get("/api/outfits").json() == []

    llm_calls.match = two_recreations(wardrobe)
    assert len(recreate(client, look_id).json()["outfits"]) == 2
    assert len(llm_calls.tag_photos) == 1                       # the photos were never sent again


def test_a_failed_tagging_saves_nothing(client, db_path, llm_calls, tmp_path):
    llm_calls.tags = UnusableResponse("no look", USAGE)
    assert post_look(client).status_code == 502
    assert client.get("/api/looks").json() == []
    assert not (tmp_path / "looks").exists() or not any((tmp_path / "looks").iterdir())


def test_an_empty_wardrobe_makes_no_matching_call(client, llm_calls):
    look_id = post_look(client).json()["id"]
    body = recreate(client, look_id).json()
    assert body["outfits"] == [] and body["look"]["recreations"] == []
    assert llm_calls.match_contexts == []


def test_the_matching_call_sees_only_owned_garments(client, db_path, wardrobe, llm_calls):
    from datetime import date
    db.insert_garment(db_path, 1, garment(weighed_on=date(2026, 11, 8)))   # being weighed
    db.insert_garment(db_path, 1, garment(disowned_on=date(2026, 11, 1)))
    llm_calls.match = two_recreations(wardrobe)
    recreate(client, post_look(client).json()["id"])
    seen = json.loads(llm_calls.match_contexts[0][0]["text"].split("\n")[1])
    assert set(seen) == {str(i) for i in wardrobe}


def test_deleting_a_look_keeps_its_outfits(client, db_path, wardrobe, llm_calls, tmp_path):
    llm_calls.match = two_recreations(wardrobe)
    look_id = post_look(client).json()["id"]
    recreate(client, look_id)
    assert client.delete(f"/api/looks/{look_id}").status_code == 204
    assert client.get("/api/looks").json() == []
    assert len(client.get("/api/outfits").json()) == 2
    assert not (tmp_path / "looks" / str(look_id)).exists()
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM look_matches").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM outfits WHERE look_id IS NOT NULL").fetchone()[0] == 0
    assert client.delete(f"/api/looks/{look_id}").status_code == 404
    assert client.get(f"/looks/{look_id}/00.jpg").status_code == 404


def test_both_calls_count_as_mimic_usage(client, wardrobe, llm_calls):
    llm_calls.match = two_recreations(wardrobe)
    recreate(client, post_look(client).json()["id"])
    kinds = [c["kind"] for c in client.get("/api/usage").json()]
    assert kinds.count("mimic") == 2


def test_too_many_photos_are_refused_before_any_call(client, llm_calls):
    assert post_look(client, n=11).status_code == 422
    assert llm_calls.tag_photos == []


def test_an_unknown_look_cant_be_recreated(client, llm_calls):
    assert recreate(client, 999).status_code == 404


def test_resetting_the_demo_clears_its_looks(db_path):
    demo_id = db.insert_demo_user(db_path, "demo")
    db.insert_look(db_path, demo_id, LOOK, None, "2026-11-10T00:00:00+00:00")
    db.delete_demo_wardrobe(db_path, demo_id, keep=set())
    assert db.select_looks(db_path, demo_id) == []


# --- the prompts --------------------------------------------------------------------------

def test_the_look_prompt_uses_the_wardrobe_field_rules_and_judges_pieces_as_worn():
    assert llm.CUT_AND_CLOTH_RULES in llm.LOOK_TAG_SYSTEM_PROMPT
    assert llm.CUT_AND_CLOTH_RULES in llm.TAG_SYSTEM_PROMPT
    assert llm.SILHOUETTE_LETTERS in llm.LOOK_TAG_SYSTEM_PROMPT
    assert "not on an average adult" in llm.LOOK_TAG_SYSTEM_PROMPT


def test_in_another_language_the_fixed_values_stay_english():
    prompt = llm.look_tag_system_prompt("ja-JP")
    assert "silhouette are fixed values" in prompt
    assert "Japanese" in prompt
    assert llm.look_tag_system_prompt("en-US") == llm.LOOK_TAG_SYSTEM_PROMPT

"""The usage page's numbers, and who can see them."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from enclothed import api, intake, outfit
from enclothed.auth import signed_in_user
from enclothed.config import DEFAULT_USER_ID, MIGRATIONS_DIR, SCHEMA_PATH
from enclothed.db import init_db
from enclothed.llm import UnusableResponse, improve_preferences, recommend_outfits, tag_garment
from enclothed.models import TokenUsage, User
from enclothed.usage import call_cost, log_failed_call, read_calls

SONNET = "claude-sonnet-5-5"
ALICE = User(id=1, username="alice", is_admin=True)
BOB = User(id=2, username="bob")


def usage_dict(input_tokens=1000, output_tokens=100, model=SONNET, **extra):
    return {"model": model, "input_tokens": input_tokens, "output_tokens": output_tokens, **extra}


def line(timestamp="2026-11-04T12:00:00+00:00", user_id=1, usage=None, **extra):
    entry = {"timestamp": timestamp, "user_id": user_id, "usage": usage_dict() if usage is None else usage, **extra}
    return json.dumps(entry)


def write_log(path, *lines):
    path.write_text("".join(text + "\n" for text in lines), encoding="utf-8")


# --- cost --------------------------------------------------
def test_cost_adds_all_four_token_types():
    usage = TokenUsage(model=SONNET, input_tokens=1_000_000, output_tokens=1_000_000,
                       cache_creation_input_tokens=1_000_000, cache_read_input_tokens=1_000_000)
    assert call_cost(usage) == pytest.approx(2.00 + 10.00 + 2.50 + 0.10)


def test_cost_of_a_typical_tagging_call():
    assert call_cost(TokenUsage(model=SONNET, input_tokens=3000, output_tokens=500)) == pytest.approx(0.011)


def test_a_model_with_no_price_has_no_cost():
    assert call_cost(TokenUsage(model="claude-future", input_tokens=10, output_tokens=10)) is None


# --- reading the logs --------------------------------------
def test_reads_every_kind_oldest_first(tmp_path):
    tagging, outfits, style = tmp_path / "t", tmp_path / "o", tmp_path / "s"
    write_log(tagging, line("2026-11-02T00:00:00+00:00"))
    write_log(outfits, line("2026-11-03T00:00:00+00:00"))
    write_log(style, line("2026-11-01T00:00:00+00:00"))
    calls = read_calls({"tagging": tagging, "outfits": outfits, "style": style})
    assert [c.kind for c in calls] == ["style", "tagging", "outfits"]


def test_cache_tokens_carry_through(tmp_path):
    log = tmp_path / "o"
    write_log(log, line(usage=usage_dict(cache_creation_input_tokens=7, cache_read_input_tokens=9)))
    [call] = read_calls({"outfits": log})
    assert (call.cache_write_tokens, call.cache_read_tokens) == (7, 9)


def test_skips_test_mode_lines_and_a_missing_log(tmp_path):
    log = tmp_path / "t"
    log.write_text(json.dumps({"timestamp": "2026-11-04T00:00:00+00:00", "user_id": 1, "usage": None}) + "\n", encoding="utf-8")
    assert read_calls({"tagging": log, "outfits": tmp_path / "nothing"}) == []


@pytest.mark.parametrize("bad", ['{"cut off', '[1, 2]', '{"usage": {"model": "x"}}', line(timestamp="not a date")])
def test_a_bad_line_is_skipped_and_the_rest_still_count(tmp_path, bad):
    log = tmp_path / "t"
    write_log(log, line(), bad, line())
    assert len(read_calls({"tagging": log})) == 2


def test_lines_from_before_accounts_belong_to_the_first_user(tmp_path):
    log = tmp_path / "t"
    log.write_text(json.dumps({"timestamp": "2026-10-20T00:00:00+00:00", "usage": usage_dict()}) + "\n", encoding="utf-8")
    assert read_calls({"tagging": log})[0].user_id == DEFAULT_USER_ID


def test_date_range_includes_from_and_excludes_to(tmp_path):
    log = tmp_path / "t"
    write_log(log, line("2026-11-01T00:00:00+00:00"), line("2026-11-02T00:00:00+00:00"), line("2026-11-03T00:00:00+00:00"))
    calls = read_calls({"tagging": log}, datetime(2026, 11, 2, tzinfo=timezone.utc), datetime(2026, 11, 3, tzinfo=timezone.utc))
    assert [c.timestamp[:10] for c in calls] == ["2026-11-02"]


# --- the API -----------------------------------------------
@pytest.fixture
def logged(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute("UPDATE users SET username = 'alice' WHERE id = 1")
            conn.execute("INSERT INTO users (id, username) VALUES (2, 'bob')")
            conn.execute("INSERT INTO users (id, username) VALUES (3, 'carol')")
    tagging, outfits, style = tmp_path / "tagging.jsonl", tmp_path / "outfit.jsonl", tmp_path / "style.jsonl"
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(api, "TAGGING_LOG_PATH", tagging)
    monkeypatch.setattr(api, "OUTFIT_LOG_PATH", outfits)
    monkeypatch.setattr(api, "PREFERENCES_LOG_PATH", style)
    write_log(tagging, line(user_id=1, prompt_message="alice's secret prompt"))
    write_log(outfits, line(user_id=2, context="bob's secret wardrobe"), line("2026-11-01T00:00:00+00:00", user_id=2))
    write_log(style, line(user_id=1, input="alice's secret style"))
    return tmp_path


@pytest.fixture
def as_user():
    def sign_in(user):
        api.app.dependency_overrides[signed_in_user] = lambda: user
        return TestClient(api.app)
    yield sign_in
    api.app.dependency_overrides.clear()


def test_people_see_only_their_own_calls(logged, as_user):
    calls = as_user(BOB).get("/api/usage").json()
    assert {c["user_id"] for c in calls} == {2}
    assert len(calls) == 2


def test_usage_filters_by_date(logged, as_user):
    calls = as_user(BOB).get("/api/usage", params={"from": "2026-11-02T00:00:00Z"}).json()
    assert len(calls) == 1


def test_a_non_admin_can_not_see_everyone(logged, as_user):
    assert as_user(BOB).get("/api/usage/all").status_code == 403


def test_an_admin_sees_everyone_including_people_with_no_calls(logged, as_user):
    body = as_user(ALICE).get("/api/usage/all").json()
    assert [u["username"] for u in body["users"]] == ["alice", "bob", "carol"]
    assert {c["user_id"] for c in body["calls"]} == {1, 2}
    assert len(body["calls"]) == 4


def test_an_admin_acting_as_someone_sees_that_persons_usage(logged, as_user):
    client = as_user(ALICE)
    client.put("/api/act-as", json={"user_id": 2})
    assert {c["user_id"] for c in client.get("/api/usage").json()} == {2}
    assert len(client.get("/api/usage/all").json()["calls"]) == 4


@pytest.mark.parametrize("path", ["/api/usage", "/api/usage/all"])
def test_no_prompts_or_wardrobe_text_in_the_response(logged, as_user, path):
    assert "secret" not in as_user(ALICE).get(path).text


# --- failed calls ------------------------------------------
def refused_client():
    usage = SimpleNamespace(input_tokens=500, output_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0)
    response = SimpleNamespace(parsed_output=None, stop_reason="refusal", usage=usage, content=[])
    return SimpleNamespace(messages=SimpleNamespace(parse=lambda **kwargs: response))


@pytest.mark.parametrize("call", [
    lambda client: tag_garment(client, []),
    lambda client: improve_preferences(client, "text"),
    lambda client: recommend_outfits(client, []),
])
def test_an_unusable_response_carries_its_usage(call):
    with pytest.raises(UnusableResponse) as raised:
        call(refused_client())
    assert raised.value.usage.input_tokens == 500


def test_a_failed_call_is_counted(tmp_path):
    log = tmp_path / "t"
    log_failed_call(log, 2, TokenUsage(model=SONNET, input_tokens=1000, output_tokens=0), "No garment in response")
    [call] = read_calls({"tagging": log})
    assert (call.user_id, call.input_tokens) == (2, 1000)


def test_add_garment_logs_a_refused_tagging_call(tmp_path, monkeypatch):
    log, staged = tmp_path / "tagging.jsonl", tmp_path / "front.jpg"
    staged.write_bytes(b"x")
    def refuse(*args):
        raise UnusableResponse("No garment in response", TokenUsage(model=SONNET, input_tokens=1000, output_tokens=0))
    monkeypatch.setattr(intake, "tag_garment", refuse)
    with pytest.raises(UnusableResponse):
        intake.add_garment(2, [str(staged)], tmp_path / "db", tmp_path, tmp_path, log, None, False)
    assert read_calls({"tagging": log})[0].user_id == 2


def test_generate_outfits_logs_a_refused_call(tmp_path, monkeypatch):
    log = tmp_path / "outfit.jsonl"
    def refuse(*args):
        raise UnusableResponse("No outfits in response", TokenUsage(model=SONNET, input_tokens=1000, output_tokens=0))
    monkeypatch.setattr(outfit, "recommend_outfits", refuse)
    with pytest.raises(UnusableResponse):
        outfit.generate_outfits(tmp_path / "db", 2, {}, None, log, None, "dinner", False)
    assert read_calls({"outfits": log})[0].user_id == 2

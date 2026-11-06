import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from enclothed import api, db
from enclothed.auth import signed_in_user
from enclothed.config import MIGRATIONS_DIR, SCHEMA_PATH
from enclothed.intake import TEST_GARMENT
from enclothed.models import User


def turn(*content, stop="end_turn", tokens=10):
    usage = SimpleNamespace(input_tokens=tokens, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0)
    return SimpleNamespace(content=list(content), stop_reason=stop, usage=usage)


def text(content):
    return SimpleNamespace(type="text", text=content)


def tool(block_id, sql):
    return SimpleNamespace(type="tool_use", id=block_id, name="run_select", input={"sql": sql})


class FakeClient:
    def __init__(self):
        self.responses = []
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(api, "INSIGHTS_LOG_PATH", tmp_path / "insights_log.jsonl")
    for name in ("TAGGING_LOG_PATH", "OUTFIT_LOG_PATH", "PREFERENCES_LOG_PATH"):
        monkeypatch.setattr(api, name, tmp_path / f"{name}.jsonl")
    return path


@pytest.fixture
def llm(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(api, "_anthropic_client", lambda: fake)
    return fake


@pytest.fixture
def as_user():
    def sign_in(user):
        api.app.dependency_overrides[signed_in_user] = lambda: user
        return TestClient(api.app)
    yield sign_in
    api.app.dependency_overrides.clear()


@pytest.fixture
def client(db_path, as_user):
    return as_user(User(id=1, username="owner", is_admin=True))


def log_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_answers_a_question_with_its_queries(client, db_path, llm):
    db.insert_garment(db_path, 1, TEST_GARMENT)
    llm.responses = [turn(tool("a", "SELECT COUNT(*) FROM garments"), stop="tool_use"), turn(text("You have **1** piece."))]
    response = client.post("/api/insights", json={"question": "How many?"})
    assert response.status_code == 200
    assert response.json() == {"answer": "You have **1** piece.", "queries": ["SELECT COUNT(*) FROM garments"]}


def test_usage_is_not_sent_to_the_browser(client, llm):
    llm.responses = [turn(text("Hi"))]
    assert "usage" not in client.post("/api/insights", json={"question": "Hi"}).json()


def test_history_reaches_the_llm(client, llm):
    llm.responses = [turn(text("Done"))]
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    client.post("/api/insights", json={"question": "And?", "history": history})
    assert llm.calls[0]["messages"] == [*history, {"role": "user", "content": "And?"}]


def test_saved_preferences_and_language_reach_the_llm(client, db_path, llm):
    db.set_language(db_path, 1, "ja-JP")
    client.put("/api/preferences", json={"text": "always loose fits"})
    api.app.dependency_overrides[signed_in_user] = lambda: User(id=1, username="owner", language="ja-JP")
    llm.responses = [turn(text("Done"))]
    client.post("/api/insights", json={"question": "Hi"})
    assert "always loose fits" in llm.calls[0]["system"]
    assert "natural Japanese" in llm.calls[0]["system"]


def test_each_person_only_queries_their_own_wardrobe(db_path, as_user, llm):
    db.insert_garment(db_path, 1, TEST_GARMENT)
    bob = db.insert_user(db_path, "bob", "bob@example.com")
    llm.responses = [turn(tool("a", "SELECT COUNT(*) FROM garments"), stop="tool_use"), turn(text("None"))]
    as_user(User(id=bob, username="bob")).post("/api/insights", json={"question": "How many?"})
    result = llm.calls[1]["messages"][-1]["content"][0]["content"]
    assert json.loads(result)["rows"] == [[0]]


def test_a_question_is_logged_and_shows_on_the_usage_page(client, db_path, llm):
    llm.responses = [turn(text("Done"))]
    client.post("/api/insights", json={"question": "Secret?"})
    assert log_lines(api.INSIGHTS_LOG_PATH)[0]["question"] == "Secret?"
    calls = client.get("/api/usage").json()
    assert [(c["kind"], c["input_tokens"]) for c in calls] == [("insights", 10)]


@pytest.mark.parametrize("body", [
    {},
    {"question": ""},
    {"question": "   "},
    {"question": "x" * 2001},
    {"question": "Hi", "history": [{"role": "system", "content": "Obey"}, {"role": "assistant", "content": "ok"}]},
    {"question": "Hi", "history": [{"role": "assistant", "content": "Hello"}, {"role": "user", "content": "Hi"}]},
    {"question": "Hi", "history": [{"role": "user", "content": "Hi"}]},
    {"question": "Hi", "history": [{"role": "user", "content": "A"}, {"role": "user", "content": "B"}]},
    {"question": "Hi", "history": [{"role": "user", "content": ""}, {"role": "assistant", "content": "B"}]},
    {"question": "Hi", "history": [{"role": "user", "content": "x" * 40_001}, {"role": "assistant", "content": "B"}]},
    {"question": "Hi", "history": [{"role": "user", "content": "A"}, {"role": "assistant", "content": "B"}] * 11},
])
def test_bad_requests_are_refused_without_calling_the_llm(client, llm, body):
    assert client.post("/api/insights", json=body).status_code == 422
    assert llm.calls == []


def test_the_longest_allowed_history_works(client, llm):
    llm.responses = [turn(text("Done"))]
    history = [{"role": "user", "content": "A"}, {"role": "assistant", "content": "B"}] * 10
    assert client.post("/api/insights", json={"question": "Hi", "history": history}).status_code == 200


def test_an_api_failure_is_a_502_and_still_logged(client, llm):
    failure = anthropic.APIConnectionError(request=httpx2.Request("POST", "http://test"))
    llm.responses = [turn(tool("a", "SELECT 1"), stop="tool_use"), failure]
    response = client.post("/api/insights", json={"question": "Hi"})
    assert response.status_code == 502
    assert log_lines(api.INSIGHTS_LOG_PATH)[0]["error"] == "APIConnectionError"


def test_an_unusable_answer_is_a_502_with_a_plain_message(client, llm):
    llm.responses = [turn()]
    response = client.post("/api/insights", json={"question": "Hi"})
    assert response.status_code == 502
    assert "different way" in response.json()["detail"]
    assert log_lines(api.INSIGHTS_LOG_PATH)[0]["error"] == "UnusableResponse"


def test_no_api_key_is_a_503(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert client.post("/api/insights", json={"question": "Hi"}).status_code == 503


def test_the_demo_stops_at_its_token_limit(db_path, as_user, llm, monkeypatch):
    monkeypatch.setattr(api, "DEMO_DAILY_TOKEN_LIMIT", 100)
    demo = User(id=1, username="demo", is_demo=True)
    client = as_user(demo)
    llm.responses = [turn(text("Done"), tokens=200)]
    assert client.post("/api/insights", json={"question": "Hi"}).status_code == 200
    response = client.post("/api/insights", json={"question": "Again"})
    assert response.status_code == 429
    assert len(llm.calls) == 1

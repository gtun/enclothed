import json
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from enclothed import config, db, insights, llm
from enclothed.usage import read_calls
from enclothed.insights import add_usage, answer_question, tool_text
from enclothed.llm import UnusableResponse, insights_system_prompt, insights_turn
from enclothed.models import QueryResult, TokenUsage
from enclothed.sandbox import insights_schema_text

OWNER = 1
OTHER = 2


def text(content):
    return SimpleNamespace(type="text", text=content)


def tool(block_id, sql, name="run_select"):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input={"sql": sql})


def turn(*content, stop="end_turn"):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_creation_input_tokens=2, cache_read_input_tokens=3)
    return SimpleNamespace(content=list(content), stop_reason=stop, usage=usage)


def tool_turn(*content):
    return turn(*content, stop="tool_use")


class FakeClient:
    """Plays back scripted responses and keeps a copy of what each call was sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def sent_results(client, call):
    """The tool_result blocks in the last message of one call."""
    return client.calls[call]["messages"][-1]["content"]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute("INSERT INTO users (id, username) VALUES (?, ?)", (OTHER, "other"))
            for user_id, brand in ((OWNER, "Mine"), (OTHER, "Theirs")):
                conn.execute(
                    "INSERT INTO garments (category, subcategory, primary_color, styling_notes, brand, user_id) "
                    "VALUES ('top', 'shirt', 'black', 'plain', ?, ?)",
                    (brand, user_id),
                )
    return path


def ask(client, db_path, history=None, question="How many?", user_id=OWNER):
    return answer_question(client, db_path, user_id, question, history or [])


# --- The loop ---------------------------------------------------------------------------

def test_a_question_needing_no_query_is_answered_in_one_turn(db_path):
    client = FakeClient(turn(text("Hello")))
    result = ask(client, db_path)
    assert result.answer == "Hello"
    assert result.queries == []
    assert len(client.calls) == 1


def test_query_results_go_back_to_the_llm(db_path):
    client = FakeClient(tool_turn(tool("a", "SELECT brand FROM garments")), turn(text("One piece")))
    result = ask(client, db_path)
    assert result.answer == "One piece"
    assert result.queries == ["SELECT brand FROM garments"]
    [sent] = sent_results(client, 1)
    assert sent["type"] == "tool_result"
    assert sent["tool_use_id"] == "a"
    assert sent["is_error"] is False
    assert json.loads(sent["content"]) == {"columns": ["brand"], "rows": [["Mine"]]}


def test_the_assistant_turn_is_kept_before_the_results(db_path):
    first = tool_turn(text("Checking"), tool("a", "SELECT 1"))
    client = FakeClient(first, turn(text("Done")))
    ask(client, db_path)
    assert [m["role"] for m in client.calls[1]["messages"]] == ["user", "assistant", "user"]
    assert client.calls[1]["messages"][1]["content"] == first.content


def test_parallel_tool_calls_share_one_user_message(db_path):
    client = FakeClient(tool_turn(tool("a", "SELECT 1"), tool("b", "SELECT 2")), turn(text("Done")))
    result = ask(client, db_path)
    assert [m["role"] for m in client.calls[1]["messages"]] == ["user", "assistant", "user"]
    assert [r["tool_use_id"] for r in sent_results(client, 1)] == ["a", "b"]
    assert result.queries == ["SELECT 1", "SELECT 2"]


def test_a_failed_query_is_reported_and_not_listed(db_path):
    client = FakeClient(tool_turn(tool("a", "SELECT nope FROM garments")), tool_turn(tool("b", "SELECT 1")), turn(text("Done")))
    result = ask(client, db_path)
    [sent] = sent_results(client, 1)
    assert sent["is_error"] is True
    assert "no such column" in sent["content"]
    assert result.queries == ["SELECT 1"]


def test_an_unknown_tool_is_reported_not_raised(db_path):
    client = FakeClient(tool_turn(tool("a", "SELECT 1", name="drop_everything")), turn(text("Done")))
    assert ask(client, db_path).queries == []
    assert sent_results(client, 1)[0]["is_error"] is True


def test_wrong_tool_arguments_are_reported_not_raised(db_path):
    block = SimpleNamespace(type="tool_use", id="a", name="run_select", input={"query": "SELECT 1"})
    client = FakeClient(tool_turn(block), turn(text("Done")))
    assert ask(client, db_path).answer == "Done"
    assert sent_results(client, 1)[0]["is_error"] is True


def test_text_before_a_tool_call_is_not_part_of_the_answer(db_path):
    client = FakeClient(tool_turn(text("Let me check"), tool("a", "SELECT 1")), turn(text("Done")))
    assert ask(client, db_path).answer == "Done"


def test_usage_is_added_up_across_turns(db_path):
    client = FakeClient(tool_turn(tool("a", "SELECT 1")), tool_turn(tool("b", "SELECT 2")), turn(text("Done")))
    usage = ask(client, db_path).usage
    assert (usage.input_tokens, usage.output_tokens) == (30, 15)
    assert (usage.cache_creation_input_tokens, usage.cache_read_input_tokens) == (6, 9)


def test_running_out_of_turns_raises_with_the_tokens_spent(db_path):
    responses = [tool_turn(tool(str(i), "SELECT 1")) for i in range(config.INSIGHTS_MAX_TURNS + 3)]
    client = FakeClient(*responses)
    with pytest.raises(UnusableResponse) as raised:
        ask(client, db_path)
    assert len(client.calls) == config.INSIGHTS_MAX_TURNS
    assert raised.value.usage.input_tokens == 10 * config.INSIGHTS_MAX_TURNS


def test_an_empty_final_answer_raises_with_the_tokens_spent(db_path):
    with pytest.raises(UnusableResponse) as raised:
        ask(FakeClient(turn()), db_path)
    assert raised.value.usage.input_tokens == 10


# --- History and isolation --------------------------------------------------------------

def test_history_comes_before_the_new_question(db_path):
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    client = FakeClient(turn(text("Done")))
    ask(client, db_path, history, "And now?")
    assert client.calls[0]["messages"] == [*history, {"role": "user", "content": "And now?"}]


def test_history_is_not_changed(db_path):
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    before = list(history)
    ask(FakeClient(tool_turn(tool("a", "SELECT 1")), turn(text("Done"))), db_path, history)
    assert history == before


def test_queries_only_see_the_askers_data(db_path):
    client = FakeClient(tool_turn(tool("a", "SELECT brand FROM garments")), turn(text("Done")))
    ask(client, db_path, user_id=OTHER)
    assert json.loads(sent_results(client, 1)[0]["content"])["rows"] == [["Theirs"]]


@pytest.mark.parametrize("responses", [
    [turn(text("Done"))],
    [turn()],
])
def test_the_copy_is_closed_however_it_ends(db_path, monkeypatch, responses):
    opened = []
    real = insights.build_snapshot

    def spy(path, user_id):
        opened.append(real(path, user_id))
        return opened[-1]

    monkeypatch.setattr(insights, "build_snapshot", spy)
    try:
        ask(FakeClient(*responses), db_path)
    except UnusableResponse:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")


# --- Logging ----------------------------------------------------------------------------

def log_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_a_question_is_logged_with_its_content(db_path, tmp_path):
    log = tmp_path / "insights.jsonl"
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
    client = FakeClient(tool_turn(tool("a", "SELECT 1")), turn(text("日本")))
    answer_question(client, db_path, OTHER, "And now?", history, log_path=log)
    [entry] = log_lines(log)
    assert entry["user_id"] == OTHER
    assert entry["messages"] == 3
    assert entry["question"] == "And now?"
    assert entry["answer"] == "日本"
    assert entry["sql"] == ["SELECT 1"]
    assert entry["error"] is None
    assert entry["usage"]["input_tokens"] == 20
    assert "日本" in log.read_text(encoding="utf-8")


def test_each_question_gets_one_line(db_path, tmp_path):
    log = tmp_path / "insights.jsonl"
    for _ in range(2):
        answer_question(FakeClient(turn(text("Done"))), db_path, OWNER, "Q", [], log_path=log)
    assert len(log_lines(log)) == 2


def test_no_log_path_writes_nothing(db_path, tmp_path):
    ask(FakeClient(turn(text("Done"))), db_path)
    assert list(tmp_path.glob("*.jsonl")) == []


def test_an_unusable_answer_is_logged_with_its_tokens(db_path, tmp_path):
    log = tmp_path / "insights.jsonl"
    with pytest.raises(UnusableResponse):
        answer_question(FakeClient(turn()), db_path, OWNER, "Q", [], log_path=log)
    [entry] = log_lines(log)
    assert entry["error"] == "UnusableResponse"
    assert entry["usage"]["input_tokens"] == 10


def test_an_api_error_partway_is_logged_with_the_tokens_so_far(db_path, tmp_path):
    class FailsSecondCall(FakeClient):
        def create(self, **kwargs):
            if self.calls:
                raise anthropic.APIConnectionError(request=httpx2.Request("POST", "http://test"))
            return super().create(**kwargs)

    log = tmp_path / "insights.jsonl"
    client = FailsSecondCall(tool_turn(tool("a", "SELECT 1")))
    with pytest.raises(anthropic.APIError):
        answer_question(client, db_path, OWNER, "Q", [], log_path=log)
    [entry] = log_lines(log)
    assert entry["error"] == "APIConnectionError"
    assert entry["answer"] is None
    assert entry["sql"] == ["SELECT 1"]
    assert entry["usage"]["input_tokens"] == 10


def test_logged_questions_reach_the_usage_page(db_path, tmp_path):
    log = tmp_path / "insights.jsonl"
    answer_question(FakeClient(turn(text("Done"))), db_path, OWNER, "Q", [], log_path=log)
    [call] = read_calls({"insights": log})
    assert (call.kind, call.user_id, call.input_tokens) == ("insights", OWNER, 10)


# --- Helpers ----------------------------------------------------------------------------

def test_tool_text_returns_an_error_as_is():
    assert tool_text(QueryResult(error="nope")) == "nope"


def test_tool_text_keeps_japanese_readable():
    assert "日本" in tool_text(QueryResult(columns=["c"], rows=[("日本",)]))


def test_tool_text_handles_blobs():
    assert json.loads(tool_text(QueryResult(columns=["b"], rows=[(b"x",)])))["rows"] == [["b'x'"]]


def test_tool_text_shows_an_empty_result():
    assert json.loads(tool_text(QueryResult(columns=["id"], rows=[]))) == {"columns": ["id"], "rows": []}


def test_add_usage_keeps_the_model_and_adds_every_count():
    one = TokenUsage(model="m", input_tokens=1, output_tokens=2, cache_creation_input_tokens=3, cache_read_input_tokens=4)
    assert add_usage(one, one) == TokenUsage(model="m", input_tokens=2, output_tokens=4, cache_creation_input_tokens=6, cache_read_input_tokens=8)


# --- The prompt and one turn ------------------------------------------------------------

def test_schema_text_lists_every_table_and_leaves_private_columns_out():
    text_ = insights_schema_text()
    assert [line.split(":")[0] for line in text_.splitlines()] == ["garments", "sets", "outfits", "outfit_garments", "wears"]
    columns = {c.split()[0] for line in text_.splitlines() for c in line.split(": ")[1].split(", ")}
    assert "notes" not in columns
    assert "user_id" not in columns


def test_the_prompt_contains_the_real_schema():
    prompt = insights_system_prompt("en-US")
    assert insights_schema_text() in prompt
    assert "<function" not in prompt


def test_preferences_are_added_only_when_given():
    assert "<preferences>\n" not in insights_system_prompt("en-US")
    assert "<preferences>\nLoose fits\n</preferences>" in insights_system_prompt("en-US", "Loose fits")


def test_another_language_adds_instructions():
    assert "Language:" not in insights_system_prompt("en-US")
    assert "Language:" in insights_system_prompt("ja-JP")


def test_a_turn_sends_the_tool_prompt_and_cache_setting():
    client = FakeClient(turn(text("Hi")))
    messages = [{"role": "user", "content": "Hi"}]
    response, usage = insights_turn(client, messages, "ja-JP", "Loose fits")
    call = client.calls[0]
    assert response.content[0].text == "Hi"
    assert (usage.input_tokens, usage.cache_read_input_tokens) == (10, 3)
    assert call["messages"] == messages
    assert call["tools"] == [llm.RUN_SELECT_TOOL]
    assert call["cache_control"] == {"type": "ephemeral"}
    assert call["max_tokens"] == config.INSIGHTS_TOKEN_CAP
    assert "Loose fits" in call["system"]

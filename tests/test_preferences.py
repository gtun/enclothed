import json

import pytest

from enclothed import preferences
from enclothed.llm import UnusableResponse
from enclothed.models import TokenUsage

USAGE = TokenUsage(model="m", input_tokens=10, output_tokens=5)


def log_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_a_rewrite_is_returned_and_logged_with_its_words_and_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "improve_preferences", lambda client, text: ("Needs:\n- glasses", USAGE))
    log = tmp_path / "preferences_log.jsonl"
    assert preferences.rewrite(None, log, 3, "i need my glasses") == "Needs:\n- glasses"
    [line] = log_lines(log)
    assert line["user_id"] == 3 and line["input"] == "i need my glasses" and line["output"] == "Needs:\n- glasses"
    assert line["usage"]["input_tokens"] == 10


def test_an_unusable_rewrite_is_logged_with_its_tokens_and_raised(tmp_path, monkeypatch):
    def unusable(client, text):
        raise UnusableResponse("No rewrite in response", USAGE)
    monkeypatch.setattr(preferences, "improve_preferences", unusable)
    log = tmp_path / "preferences_log.jsonl"
    with pytest.raises(UnusableResponse):
        preferences.rewrite(None, log, 3, "navy")
    [line] = log_lines(log)
    assert line["error"] == "No rewrite in response" and line["usage"]["output_tokens"] == 5

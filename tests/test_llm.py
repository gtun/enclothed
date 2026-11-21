# The provider seams in llm.py: the client, its errors, and the insights conversation.
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from enclothed import config, llm
from enclothed.models import ImprovedPreferences


def usage(**counts):
    return SimpleNamespace(**{"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": None,
                              "cache_read_input_tokens": None, **counts})


def sdk(parse=None, create=None):
    return SimpleNamespace(messages=SimpleNamespace(parse=parse, create=create))


# --- make_client ----------------------------------------------------------------------------

def test_a_missing_key_is_named(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.MissingKey, match="ANTHROPIC_API_KEY"):
        llm.make_client()


def test_the_client_is_for_the_configured_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")   # building the SDK client makes no call
    client = llm.make_client()
    assert client.provider == config.LLM_PROVIDER == "anthropic"
    assert isinstance(client.sdk, anthropic.Anthropic)


def test_every_provider_has_a_key_variable():
    assert set(config.MODELS_BY_PROVIDER) == set(llm.API_KEY_VARIABLES)


# --- errors ---------------------------------------------------------------------------------

def refused(**kwargs):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(400, request=request, headers={"request-id": "req_123"})
    raise anthropic.BadRequestError("Schema is too complex.", response=response, body=None)


def test_an_sdk_error_becomes_a_service_error_with_its_name_and_request_id():
    with pytest.raises(llm.ServiceError) as raised:
        llm.improve_preferences(llm.Client("anthropic", sdk(parse=refused)), "I like navy")
    assert raised.value.message == "Schema is too complex."
    assert raised.value.kind == "BadRequestError"
    assert raised.value.request_id == "req_123"
    assert isinstance(raised.value.__cause__, anthropic.BadRequestError)


def test_an_insights_turn_raises_service_errors_too():
    chat = llm.InsightsChat(llm.Client("anthropic", sdk(create=refused)), [], "Hi")
    with pytest.raises(llm.ServiceError):
        chat.next_turn()


def test_errors_that_arent_the_sdks_pass_through():
    def broken(**kwargs):
        raise ValueError("not the API")
    with pytest.raises(ValueError):
        llm.improve_preferences(llm.Client("anthropic", sdk(parse=broken)), "I like navy")


# --- structured calls -----------------------------------------------------------------------

def test_a_structured_call_reports_cache_tokens_and_cut_off():
    response = SimpleNamespace(parsed_output=ImprovedPreferences(text="x"), stop_reason="max_tokens",
                               usage=usage(cache_creation_input_tokens=7, cache_read_input_tokens=3))
    reply = llm._parse(llm.Client("anthropic", sdk(parse=lambda **kwargs: response)), "preferences", "system", "hi",
                       ImprovedPreferences, 100)
    assert (reply.usage.cache_creation_input_tokens, reply.usage.cache_read_input_tokens) == (7, 3)
    assert reply.usage.model == config.MODELS["preferences"]
    assert reply.cut_off is True


# --- the insights conversation --------------------------------------------------------------

def tool_block(block_id="a"):
    return SimpleNamespace(type="tool_use", id=block_id, name="run_select", input={"sql": "SELECT 1"})


def test_tool_calls_come_back_only_when_the_model_stopped_to_use_them():
    """A reply cut off at max_tokens can end in a half-written tool call. It's treated as the answer, as before."""
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="Partly"), tool_block()],
                               stop_reason="max_tokens", usage=usage())
    turn = llm.InsightsChat(llm.Client("anthropic", sdk(create=lambda **kwargs: response)), [], "Hi").next_turn()
    assert turn.tool_calls == []
    assert turn.text == "Partly"


def test_tool_results_follow_the_turn_that_asked_for_them():
    sent = []
    responses = [SimpleNamespace(content=[tool_block("a")], stop_reason="tool_use", usage=usage()),
                 SimpleNamespace(content=[SimpleNamespace(type="text", text="Done")], stop_reason="end_turn", usage=usage())]
    def create(**kwargs):
        sent.append(list(kwargs["messages"]))
        return responses.pop(0)
    chat = llm.InsightsChat(llm.Client("anthropic", sdk(create=create)), [], "Hi")

    [call] = chat.next_turn().tool_calls
    assert (call.id, call.name, call.arguments) == ("a", "run_select", {"sql": "SELECT 1"})
    chat.add_tool_results([llm.ToolResult(call_id="a", content="[]", is_error=False)])
    assert chat.next_turn().text == "Done"

    assert sent[1][1] == {"role": "assistant", "content": [tool_block("a")]}
    assert sent[1][2] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "a", "content": "[]", "is_error": False}]}

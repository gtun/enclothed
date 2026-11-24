# The provider seams in llm.py: the client, its errors, the content it sends, and the insights conversation.
import base64
from types import SimpleNamespace

import anthropic
import httpx
import openai
import pytest
from openai.lib._pydantic import to_strict_json_schema
from pydantic import create_model

from enclothed import config, llm
from enclothed.models import (MENDABLE_FIELDS, ImprovedPreferences, LookReply, MimicResult, OutfitDescription, OutfitResult,
                              TaggedGarment, TaggingReply, WeighResult)


def usage(**counts):
    return SimpleNamespace(**{"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": None,
                              "cache_read_input_tokens": None, **counts})


def sdk(parse=None, create=None):
    return SimpleNamespace(messages=SimpleNamespace(parse=parse, create=create))


# --- make_client ----------------------------------------------------------------------------

def test_a_missing_key_is_named(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.NotConfigured, match="ANTHROPIC_API_KEY"):
        llm.make_client()


def test_the_client_is_for_the_configured_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")   # building the SDK client makes no call
    client = llm.make_client()
    assert client.provider == config.LLM_PROVIDER == "anthropic"   # conftest clears the .env override
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
    assert reply.usage.model == llm.model_for("anthropic", "preferences")
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


# --- choosing the provider ------------------------------------------------------------------

def test_the_env_setting_picks_the_provider(monkeypatch):
    monkeypatch.setenv("ENCLOTHED_LLM_PROVIDER", "openai")
    assert llm.active_provider() == "openai"


def test_an_unknown_provider_is_named(monkeypatch):
    monkeypatch.setenv("ENCLOTHED_LLM_PROVIDER", "gemini")
    with pytest.raises(llm.NotConfigured, match="'gemini'"):
        llm.make_client()


def test_an_openai_client_needs_the_openai_key(monkeypatch):
    monkeypatch.setenv("ENCLOTHED_LLM_PROVIDER", "openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(llm.NotConfigured, match="OPENAI_API_KEY"):
        llm.make_client()


def test_an_openai_client(monkeypatch):
    monkeypatch.setenv("ENCLOTHED_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")   # building the SDK client makes no call
    client = llm.make_client()
    assert client.provider == "openai"
    assert isinstance(client.sdk, openai.OpenAI)


def test_every_model_has_a_price():
    for models in config.MODELS_BY_PROVIDER.values():
        assert set(models.values()) <= set(config.MODEL_PRICES)


# --- OpenAI structured calls ----------------------------------------------------------------

def openai_usage(input_tokens=1000, cached=0, written=0, output=50, reasoning=30):
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output,
                           input_tokens_details=SimpleNamespace(cached_tokens=cached, cache_write_tokens=written),
                           output_tokens_details=SimpleNamespace(reasoning_tokens=reasoning))


def message(*parts, phase=None):
    return SimpleNamespace(type="message", phase=phase, content=list(parts))


def output_text(text):
    return SimpleNamespace(type="output_text", text=text)


def openai_response(*output, status="completed", reason=None, usage=None):
    return SimpleNamespace(output=list(output), status=status, usage=usage or openai_usage(),
                           incomplete_details=SimpleNamespace(reason=reason) if reason else None)


class OpenAIFake(llm.Client):
    """responses.create that keeps what it was sent and answers with one scripted response."""
    def __init__(self, response):
        super().__init__("openai", self)
        self.response = response
        self.sent = None
        self.responses = self

    def create(self, **kwargs):
        self.sent = kwargs
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def preferences_call(client):
    return llm._parse(client, "preferences", "Be brief.", "I like navy", ImprovedPreferences, 100)


def test_an_openai_call_sends_the_settings_decided_for_it():
    client = OpenAIFake(openai_response(message(output_text('{"text": "Navy"}'))))
    reply = preferences_call(client)
    assert reply.parsed == ImprovedPreferences(text="Navy")
    sent = client.sent
    assert sent["model"] == config.MODELS_BY_PROVIDER["openai"]["preferences"]
    assert sent["store"] is False
    assert sent["instructions"] == "Be brief."
    assert sent["input"] == [{"role": "user", "content": "I like navy"}]
    assert sent["max_output_tokens"] == 100 + config.OPENAI_REASONING_ALLOWANCE
    assert sent["reasoning"] == {"effort": "low"}
    schema = sent["text"]["format"]
    assert (schema["type"], schema["name"], schema["strict"]) == ("json_schema", "ImprovedPreferences", True)
    assert schema["schema"]["additionalProperties"] is False


def test_content_blocks_are_sent_in_openais_shape(tmp_path):
    photo = tmp_path / "front.jpg"
    photo.write_bytes(b"jpeg")
    blocks = [{"type": "text", "text": "<wardrobe>", "cache_control": {"type": "ephemeral"}}, llm.image_block(photo)]
    assert llm._openai_content(blocks) == [
        {"type": "input_text", "text": "<wardrobe>", "prompt_cache_breakpoint": {"mode": "explicit"}},
        {"type": "input_image", "image_url": "data:image/jpeg;base64,anBlZw==", "detail": config.OPENAI_IMAGE_DETAIL},
    ]


def test_photos_are_numbered_in_order_so_the_reply_can_name_them(tmp_path):
    paths = [tmp_path / "a.jpg", tmp_path / "b.png"]
    for path in paths:
        path.write_bytes(b"photo")
    blocks = llm.photo_blocks(paths)
    assert [block.get("text") for block in blocks[::2]] == ["Image 0:", "Image 1:"]
    assert blocks[1::2] == [llm.image_block(path) for path in paths]
    assert [block["source"]["media_type"] for block in blocks[1::2]] == ["image/jpeg", "image/png"]
    assert llm.photo_blocks([]) == []


def test_caching_is_explicit_so_calls_without_a_breakpoint_write_nothing():
    """The implicit default writes the whole prompt every call, at 1.25x, and tagging's photos are never sent again."""
    client = OpenAIFake(openai_response(message(output_text('{"text": "x"}'))))
    preferences_call(client)
    assert client.sent["prompt_cache_options"] == {"mode": "explicit"}
    assert "prompt_cache_breakpoint" not in str(client.sent["input"])


def test_the_outfit_wardrobe_is_the_one_cache_breakpoint():
    from enclothed.outfit import wardrobe_block
    client = OpenAIFake(openai_response(message(output_text('{"outfits": []}'))))
    llm.recommend_outfits(client, [wardrobe_block({"1": {"category": "top"}}, caching=True), {"type": "text", "text": "<request>"}])
    first, second = client.sent["input"][0]["content"]
    assert first["prompt_cache_breakpoint"] == {"mode": "explicit"}
    assert "prompt_cache_breakpoint" not in second


def test_no_breakpoint_when_the_caller_turns_caching_off():
    from enclothed.outfit import wardrobe_block
    [part] = llm._openai_content([wardrobe_block({"1": {"category": "top"}}, caching=False)])
    assert "prompt_cache_breakpoint" not in part


def test_a_block_with_no_openai_form_is_refused():
    with pytest.raises(ValueError):
        llm._openai_content([{"type": "document", "source": {}}])


def test_openai_usage_counts_each_input_token_once():
    """OpenAI's input_tokens includes cached and cache-written tokens; TokenUsage keeps them apart, as Anthropic does."""
    client = OpenAIFake(openai_response(message(output_text('{"text": "x"}')),
                                        usage=openai_usage(input_tokens=1000, cached=300, written=200, output=80)))
    usage = preferences_call(client).usage
    assert (usage.input_tokens, usage.cache_read_input_tokens, usage.cache_creation_input_tokens) == (500, 300, 200)
    assert usage.output_tokens == 80   # reasoning is billed as output, so it stays in


def test_a_reply_cut_off_keeps_its_usage():
    """responses.parse would raise on the half-written JSON and lose the usage, which was billed."""
    client = OpenAIFake(openai_response(message(output_text('{"text": "Na')), status="incomplete", reason="max_output_tokens"))
    reply = preferences_call(client)
    assert reply.parsed is None
    assert reply.cut_off is True
    assert reply.stop_reason == "max_output_tokens"
    assert reply.usage.output_tokens == 50


def test_running_out_while_reasoning_is_unusable_with_its_usage():
    client = OpenAIFake(openai_response(SimpleNamespace(type="reasoning"), status="incomplete", reason="max_output_tokens"))
    with pytest.raises(llm.UnusableResponse, match="max_output_tokens") as raised:
        llm.improve_preferences(client, "I like navy")
    assert raised.value.usage.input_tokens == 1000


def test_a_refusal_parses_to_nothing():
    client = OpenAIFake(openai_response(message(SimpleNamespace(type="refusal", refusal="No."))))
    reply = preferences_call(client)
    assert (reply.parsed, reply.stop_reason) == (None, "refusal")


def test_only_the_final_answer_is_parsed():
    client = OpenAIFake(openai_response(message(output_text("Thinking it over"), phase="commentary"),
                                        message(output_text('{"text": "Navy"}'), phase="final_answer")))
    assert preferences_call(client).parsed == ImprovedPreferences(text="Navy")


def test_an_openai_error_becomes_a_service_error_with_its_request_id():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(429, request=request, headers={"x-request-id": "req_abc"})
    client = OpenAIFake(openai.RateLimitError("Slow down.", response=response, body=None))
    with pytest.raises(llm.ServiceError) as raised:
        preferences_call(client)
    assert (raised.value.kind, raised.value.request_id) == ("RateLimitError", "req_abc")


# --- every output schema works in OpenAI's strict mode ---------------------------------------
# Strict mode refuses some JSON Schema keywords and has size limits; a refused schema fails every call that uses it.
# https://developers.openai.com/api/docs/guides/structured-outputs (supported schemas)

UNSUPPORTED_KEYWORDS = {"allOf", "not", "if", "then", "else", "dependentRequired", "dependentSchemas",
                        "minLength", "maxLength", "patternProperties"}
OUTPUT_MODELS = [TaggingReply, LookReply, ImprovedPreferences, OutfitDescription, OutfitResult, WeighResult, MimicResult,
                 create_model("BlankFields", **{field: (TaggedGarment.model_fields[field].annotation, TaggedGarment.model_fields[field])
                                                for field in MENDABLE_FIELDS})]   # mend, with every field blank


def schema_nodes(node, under_properties=False):
    """Every schema in the tree. Under "properties" the keys are field names, not keywords."""
    if isinstance(node, dict):
        if not under_properties:
            yield node
        for key, value in node.items():
            yield from schema_nodes(value, key == "properties" and not under_properties)
    elif isinstance(node, list):
        for value in node:
            yield from schema_nodes(value)


@pytest.mark.parametrize("model", OUTPUT_MODELS, ids=lambda model: model.__name__)
def test_the_output_schema_fits_openais_strict_mode(model):
    schema = to_strict_json_schema(model)
    nodes = list(schema_nodes(schema))
    objects = [node for node in nodes if "properties" in node]
    assert not {key for node in nodes for key in node} & UNSUPPORTED_KEYWORDS
    assert all(node.get("additionalProperties") is False for node in objects)
    assert all(set(node["required"]) == set(node["properties"]) for node in objects)
    assert sum(len(node["properties"]) for node in objects) <= 5000
    assert sum(len(node["enum"]) for node in nodes if "enum" in node) <= 1000


def test_a_client_can_be_made_for_a_named_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = llm.make_client("openai")   # the default is still anthropic
    assert client.provider == "openai" and isinstance(client.sdk, openai.OpenAI)


def test_a_client_for_an_unknown_provider_is_refused():
    with pytest.raises(llm.NotConfigured, match="'gemini'"):
        llm.make_client("gemini")


def test_every_feature_has_an_openai_reasoning_effort():
    assert set(config.OPENAI_REASONING_EFFORT) == set(config.OPENAI_MODELS)
    assert set(config.OPENAI_REASONING_EFFORT.values()) <= {"low", "medium", "high"}


def test_claude_models_that_always_think_get_room_to_think():
    assert llm.anthropic_token_cap("claude-opus-5-5", 2048) == 2048 + config.ANTHROPIC_THINKING_ALLOWANCE
    assert llm.anthropic_token_cap("claude-haiku-5-5", 2048) == 2048 + config.ANTHROPIC_THINKING_ALLOWANCE
    assert llm.anthropic_token_cap("claude-sonnet-5-5", 2048) == 2048


def test_a_structured_call_on_opus_sends_the_cap_with_thinking_room(monkeypatch):
    monkeypatch.setitem(config.ANTHROPIC_MODELS, "preferences", "claude-opus-5-5")
    sent = {}
    def parse(**kwargs):
        sent.update(kwargs)
        return SimpleNamespace(parsed_output=ImprovedPreferences(text="Navy"), usage=usage(), stop_reason="end_turn")
    llm._parse(llm.Client("anthropic", sdk(parse=parse)), "preferences", "Be brief.", "I like navy", ImprovedPreferences, 100)
    assert sent["max_tokens"] == 100 + config.ANTHROPIC_THINKING_ALLOWANCE


def test_every_configured_model_has_a_display_name():
    models = {m for provider in config.MODELS_BY_PROVIDER.values() for m in provider.values()}
    assert models <= set(config.MODEL_NAMES)
    assert set(config.MODELS_BY_PROVIDER) <= set(config.PROVIDER_NAMES)


# --- garment previews -----------------------------------------------------------------------

def image_sdk(edit):
    return SimpleNamespace(images=SimpleNamespace(edit=edit))


def image_usage_reply(data):
    usage = SimpleNamespace(input_tokens=1300, output_tokens=900, total_tokens=2200,
                            input_tokens_details=SimpleNamespace(text_tokens=100, image_tokens=1200))
    return SimpleNamespace(data=data, usage=usage)


def test_a_preview_sends_the_photo_and_instruction_and_returns_the_image(tmp_path):
    photo = tmp_path / "front_00.jpg"
    photo.write_bytes(b"photo bytes")
    sent = {}

    def edit(**kwargs):
        sent.update(kwargs, image=kwargs["image"].read())
        return image_usage_reply([SimpleNamespace(b64_json=base64.b64encode(b"edited").decode())])

    image, usage = llm.preview_garment(llm.Client("openai", image_sdk(edit)), photo, "Make it bright blue", "low")
    assert image == b"edited"
    assert sent["image"] == b"photo bytes"
    assert "Make it bright blue" in sent["prompt"]
    assert (sent["model"], sent["quality"], sent["n"]) == (config.PREVIEW_MODEL, "low", 1)
    assert usage.model_dump() == {"model": config.PREVIEW_MODEL, "text_input_tokens": 100, "image_input_tokens": 1200, "output_tokens": 900}


def test_a_preview_without_an_image_still_reports_its_tokens(tmp_path):
    photo = tmp_path / "front_00.jpg"
    photo.write_bytes(b"photo bytes")
    with pytest.raises(llm.UnusableResponse) as raised:
        llm.preview_garment(llm.Client("openai", image_sdk(lambda **kwargs: image_usage_reply([]))), photo, "Make it blue")
    assert raised.value.usage.output_tokens == 900


def test_previews_need_an_openai_client(tmp_path):
    with pytest.raises(llm.NotConfigured):
        llm.preview_garment(llm.Client("anthropic", sdk()), tmp_path / "front_00.jpg", "Make it blue")

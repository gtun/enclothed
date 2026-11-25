import anthropic
import openai
from openai.lib._pydantic import to_strict_json_schema
from enclothed import config
from enclothed.models import DEFAULT_LANGUAGE, Garment, ImageUsage, Language, TaggedGarment, TaggingReply, TaggingResult, TokenUsage, blank_unknowns, to_tagging_result, OutfitResult, OutfitDescription, ImprovedPreferences, WeighResult, LookReply, LookTags, MimicResult, to_look_tags
from enclothed.prompts import (
    MEND_RULES, PREFERENCES_SYSTEM_PROMPT, PREVIEW_PROMPT, describe_system_prompt, insights_system_prompt, look_tag_system_prompt,
    outfit_system_prompt, tag_system_prompt,
)
import base64
import json
import mimetypes
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import logging
from typing import Any
from pydantic import TypeAdapter, ValidationError, create_model

logger = logging.getLogger(__name__)


class UnusableResponse(RuntimeError):
    """The LLM answered, so the tokens are spent, but with nothing we can use."""
    def __init__(self, message: str, usage: TokenUsage | ImageUsage):
        super().__init__(message)
        self.usage = usage


class ServiceError(RuntimeError):
    """The provider refused the call or never answered, so no tokens were spent. Every provider's SDK errors become
    this, so callers catch one type whichever provider ran."""
    def __init__(self, message: str, kind: str, request_id: str | None = None):
        super().__init__(message)
        self.message = message
        self.kind = kind                # the SDK's name for the error, such as RateLimitError
        self.request_id = request_id    # what the provider's support asks for


class NotConfigured(RuntimeError):
    """The provider setting names no provider, or the provider's API key isn't set, so AI features are off."""


@dataclass
class Client:
    """The provider's SDK client. Only llm.py looks inside, so the rest of the app doesn't depend on the provider."""
    provider: str
    sdk: Any


API_KEY_VARIABLES = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
PROVIDER_VARIABLE = "ENCLOTHED_LLM_PROVIDER"


def active_provider() -> str:
    """ENCLOTHED_LLM_PROVIDER if it's set, otherwise config.LLM_PROVIDER. Read at each call, since .env loads late."""
    provider = os.getenv(PROVIDER_VARIABLE) or config.LLM_PROVIDER
    if provider not in config.MODELS_BY_PROVIDER:
        raise NotConfigured(f"{PROVIDER_VARIABLE} is {provider!r}, but the providers are {', '.join(config.MODELS_BY_PROVIDER)}.")
    return provider


def model_for(provider: str, feature: str) -> str:
    return config.MODELS_BY_PROVIDER[provider][feature]


def make_client(provider: str | None = None) -> Client:
    """A client for provider, or for the active one when that's None. Raises NotConfigured when there's no such
    provider or its key isn't set."""
    provider = provider or active_provider()
    if provider not in config.MODELS_BY_PROVIDER:
        raise NotConfigured(f"There's no LLM provider named {provider!r}.")
    variable = API_KEY_VARIABLES[provider]
    if not os.getenv(variable):
        raise NotConfigured(f"No {variable} is set in .env, so AI features are off.")
    sdk = openai.OpenAI() if provider == "openai" else anthropic.Anthropic()
    return Client(provider, sdk)


@contextmanager
def _service_errors():
    """Turn the SDKs' errors into ServiceError."""
    try:
        yield
    except (anthropic.APIError, openai.APIError) as error:
        raise ServiceError(error.message, type(error).__name__, getattr(error, "request_id", None)) from error


def _usage(model: str, usage: Any) -> TokenUsage:
    return TokenUsage(
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
        cache_read_input_tokens=usage.cache_read_input_tokens or 0,
    )


def _openai_usage(model: str, usage: Any) -> TokenUsage:
    """OpenAI's input_tokens includes the cached and cache-written tokens, and Anthropic's excludes them. TokenUsage
    follows Anthropic, so each input token is counted once, at its own price. output_tokens includes reasoning."""
    details = usage.input_tokens_details
    cached = details.cached_tokens or 0
    written = details.cache_write_tokens or 0
    logger.debug("reasoning tokens: %s", usage.output_tokens_details.reasoning_tokens)
    return TokenUsage(
        model=model,
        input_tokens=usage.input_tokens - cached - written,
        output_tokens=usage.output_tokens,
        cache_creation_input_tokens=written,
        cache_read_input_tokens=cached,
    )


def _openai_content(content: str | list[dict]) -> str | list[dict]:
    """The content blocks callers build, which are Anthropic's, in the Responses API's shape. A block marked with
    cache_control (the wardrobe) gets an explicit cache breakpoint, so on both providers the prompt is cached up to
    that block and nowhere else."""
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if block["type"] == "text":
            part = {"type": "input_text", "text": block["text"]}
        elif block["type"] == "image":
            source = block["source"]
            part = {"type": "input_image", "image_url": f"data:{source['media_type']};base64,{source['data']}",
                    "detail": config.OPENAI_IMAGE_DETAIL}
        else:
            raise ValueError(f"No OpenAI form for a {block['type']!r} block")
        if block.get("cache_control"):
            part["prompt_cache_breakpoint"] = {"mode": "explicit"}
        parts.append(part)
    return parts


def _openai_answer(response: Any) -> tuple[str, bool]:
    """The reply's final-answer text, and whether it refused. Messages in another phase, such as commentary,
    aren't the answer."""
    texts, refused = [], False
    for item in response.output:
        if item.type != "message" or getattr(item, "phase", None) not in (None, "final_answer"):
            continue
        for part in item.content:
            if part.type == "output_text":
                texts.append(part.text)
            elif part.type == "refusal":
                refused = True
    return "".join(texts), refused


@dataclass
class _Reply[T]:
    parsed: T | None        # None when the reply had nothing to parse, such as a refusal
    usage: TokenUsage
    stop_reason: str | None
    cut_off: bool           # the reply hit the token cap


def anthropic_token_cap(model: str, token_cap: int) -> int:
    """max_tokens for a Claude call: the feature's cap, plus room to think on the models that always think first."""
    return token_cap + (config.ANTHROPIC_THINKING_ALLOWANCE if model in config.ANTHROPIC_THINKING_MODELS else 0)


def _parse[T](client: Client, feature: str, system: str, content: str | list[dict], output_format: type[T], token_cap: int) -> _Reply[T]:
    """One structured call on the provider's model for feature, with content as the only user message."""
    model = model_for(client.provider, feature)
    if client.provider == "openai":
        return _parse_openai(client, feature, model, system, content, output_format, token_cap)
    with _service_errors():
        response = client.sdk.messages.create(
            model=model,
            max_tokens=anthropic_token_cap(model, token_cap),
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"format": _anthropic_output_format(output_format)},
        )
    usage = _usage(model, response.usage)
    logger.debug("%s tokens: in=%s out=%s cache_creation=%s cache_read=%s", feature, usage.input_tokens, usage.output_tokens, usage.cache_creation_input_tokens, usage.cache_read_input_tokens)
    parsed = _anthropic_parsed(response, output_format)
    return _Reply(parsed, usage, response.stop_reason, response.stop_reason == "max_tokens")


def _anthropic_output_format(output_format: type) -> dict:
    """The JSON schema Claude must answer in, built the way the SDK's messages.parse builds it."""
    return {"schema": anthropic.transform_schema(TypeAdapter(output_format).json_schema()), "type": "json_schema"}


def _anthropic_parsed[T](response: Any, output_format: type[T]) -> T | None:
    """The reply's JSON as output_format, or None when there's none that fits. Parsed here rather than by
    messages.parse: that raises on JSON cut off at the token cap, as when the reply runs on until it's stopped,
    and the usage, which was billed, would be lost with it. Same as _parse_openai."""
    for block in response.content:
        if block.type != "text" or not block.text:
            continue
        try:
            return TypeAdapter(output_format).validate_json(block.text)
        except ValidationError as error:
            logger.warning("Claude reply didn't match %s (stop_reason=%s): %s", getattr(output_format, "__name__", output_format),
                           response.stop_reason, str(error)[:300])
    return None


def _parse_openai[T](client: Client, feature: str, model: str, system: str, content: str | list[dict], output_format: type[T], token_cap: int) -> _Reply[T]:
    """responses.create with a strict schema, parsed here rather than by responses.parse: that raises on JSON cut
    off at the token cap, and the usage, which was billed, would be lost with it."""
    with _service_errors():
        response = client.sdk.responses.create(
            model=model,
            instructions=system,
            input=[{"role": "user", "content": _openai_content(content)}],
            text={"format": {"type": "json_schema", "name": output_format.__name__,
                             "schema": to_strict_json_schema(output_format), "strict": True}},
            max_output_tokens=token_cap + config.OPENAI_REASONING_ALLOWANCE,
            reasoning={"effort": config.OPENAI_REASONING_EFFORT[feature]},
            # Explicit: cache only at the breakpoints above. The implicit default put its one breakpoint near the end
            # of the prompt, after the request, so the next call couldn't reuse it; every call paid 1.25x to write
            # its whole prompt (photos included) and read back almost nothing.
            prompt_cache_options={"mode": "explicit"},
            store=False,
        )
    usage = _openai_usage(model, response.usage)
    logger.debug("tokens: in=%s out=%s cache_creation=%s cache_read=%s", usage.input_tokens, usage.output_tokens, usage.cache_creation_input_tokens, usage.cache_read_input_tokens)

    incomplete = response.incomplete_details.reason if response.incomplete_details else None
    text, refused = _openai_answer(response)
    parsed = None
    if text and not refused:
        try:
            parsed = output_format.model_validate_json(text)
        except ValidationError as error:
            logger.warning("OpenAI reply didn't match %s (status=%s): %s", output_format.__name__, response.status, error)
    stop_reason = incomplete or ("refusal" if refused else response.status)
    return _Reply(parsed, usage, stop_reason, incomplete == "max_output_tokens")


RUN_SELECT_TOOL = {
    "name": "run_select",
    "description": (
        "Run one read-only SQLite query on the user's wardrobe and get the matching rows back. "
        "Only SELECT queries work, including WITH. If the query fails or the result is too large, "
        "you get an error message instead of rows: read it, fix the query, and try again."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": (
                    "A single SQLite SELECT statement. Select only the columns and rows needed to answer the question."
                ),
            },
        },
        "required": ["sql"],
    },
}


def image_block(path: Path) -> dict:
    media_type, _ = mimetypes.guess_type(path)
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data}
    }


def photo_blocks(paths: list[Path]) -> list[dict]:
    """Each photo labeled with its number ("Image 0:", then the photo, and so on), so the reply can refer to it."""
    blocks = []
    for i, path in enumerate(paths):
        blocks.append({"type": "text", "text": f"Image {i}:"})
        blocks.append(image_block(path))
    return blocks


def preview_garment(client: Client, photo_path: Path, instruction: str, quality: str = config.PREVIEW_QUALITY) -> tuple[bytes, ImageUsage]:
    """The garment's photo edited by the instruction, as image bytes, and the call's tokens. Only the photo and the
    instruction are sent: nothing from the garment's record. OpenAI only, since Claude makes no images."""
    if client.provider != "openai":
        raise NotConfigured("Garment previews need an OpenAI client: Claude makes no images.")
    model = config.PREVIEW_MODEL
    with _service_errors(), photo_path.open("rb") as photo:
        response = client.sdk.images.edit(model=model, image=photo, prompt=PREVIEW_PROMPT.format(instruction=instruction),
                                          quality=quality, size="auto", n=1)
    usage = _image_usage(model, response.usage)
    if not response.data or not response.data[0].b64_json:
        raise UnusableResponse("No image in the response", usage)
    return base64.b64decode(response.data[0].b64_json), usage


def _image_usage(model: str, usage: Any) -> ImageUsage:
    if usage is None:   # the SDK types it as optional
        logger.warning("%s returned no usage, so this call's cost is unknown", model)
        return ImageUsage(model=model, text_input_tokens=0, image_input_tokens=0, output_tokens=0)
    details = usage.input_tokens_details
    return ImageUsage(model=model, text_input_tokens=details.text_tokens, image_input_tokens=details.image_tokens,
                      output_tokens=usage.output_tokens)


def tag_garment(client: Client, photo_paths: list[Path], prompt_message: str | None = None, language: Language = DEFAULT_LANGUAGE, preferences: str | None = None) -> tuple[TaggingResult, TokenUsage]:
    content = photo_blocks(photo_paths)
    content.append({"type": "text", "text": "Tag this garment and assign a role to each image."})
    if prompt_message:
        content.append({"type": "text", "text": f"Additional context from the owner: {prompt_message}"})
    if preferences:
        content.append({"type": "text", "text": f"The owner's preferences, to use only when judging hem:\n<preferences>\n{preferences}\n</preferences>"})

    # TaggingReply, not TaggingResult: see the note above TaggedGarment in models.py
    reply = _parse(client, "tag", tag_system_prompt(language), content, TaggingReply, config.TAG_TOKEN_CAP)
    usage = reply.usage
    if reply.parsed is None:
        raise UnusableResponse(f"No garment in response (stop_reason={reply.stop_reason})", usage)
    try:
        return to_tagging_result(reply.parsed), usage
    except ValidationError as error:
        raise UnusableResponse(f"Tagged garment didn't validate: {error}", usage) from error

def tag_look(client: Client, photo_paths: list[Path], note: str | None = None, language: Language = DEFAULT_LANGUAGE) -> tuple[LookTags, TokenUsage]:
    """mimic, step 1: the only call that sees the look's photos. Everything after works from what it returns."""
    content = photo_blocks(photo_paths)
    content.append({"type": "text", "text": "Break down this look, piece by piece."})
    if note:
        content.append({"type": "text", "text": f"The owner's note about the look:\n<note>\n{note}\n</note>"})

    reply = _parse(client, "look", look_tag_system_prompt(language), content, LookReply, config.LOOK_TAG_TOKEN_CAP)
    usage = reply.usage
    if reply.cut_off:
        logger.warning("Look tagging cut off at max_tokens (%s)", config.LOOK_TAG_TOKEN_CAP)
    if reply.parsed is None:
        raise UnusableResponse(f"No look in response (stop_reason={reply.stop_reason})", usage)
    try:
        tags = to_look_tags(reply.parsed)
    except ValidationError as error:
        raise UnusableResponse(f"Tagged look didn't validate: {error}", usage) from error
    if not tags.pieces:
        raise UnusableResponse("No pieces found in the look", usage)
    return tags, usage


def fill_blanks(client: Client, photo_paths: list[Path], record: dict, blanks: list[str], language: Language = DEFAULT_LANGUAGE, preferences: str | None = None) -> tuple[dict[str, Any], TokenUsage]:
    """Ask for only the blank fields of a garment that's already in the wardrobe."""
    # Required fields with "unknown" values, like tagging, so even a garment with every field blank stays under the
    # API's schema limits (with "value or nothing" fields, 17 blanks were enough to fail).
    answers = create_model("BlankFields", **{field: (TaggedGarment.model_fields[field].annotation, TaggedGarment.model_fields[field]) for field in blanks})

    content = photo_blocks(photo_paths)
    content.append({"type": "text", "text": f"<record>\n{json.dumps(record, ensure_ascii=False)}\n</record>"})
    content.append({"type": "text", "text": f"Fill in only these blank fields: {', '.join(blanks)}"})
    if preferences:
        content.append({"type": "text", "text": f"The owner's preferences, to use only when judging hem:\n<preferences>\n{preferences}\n</preferences>"})

    reply = _parse(client, "mend", tag_system_prompt(language) + MEND_RULES, content, answers, config.MEND_TOKEN_CAP)
    usage = reply.usage
    if reply.parsed is None:
        raise UnusableResponse(f"No fields in response (stop_reason={reply.stop_reason})", usage)
    answered = blank_unknowns(reply.parsed.model_dump(mode="json"))
    return {field: value for field, value in answered.items() if value is not None}, usage


def improve_preferences(client: Client, text: str) -> tuple[str, TokenUsage]:
    """Rewrite the user's preferences so the outfit LLM can follow them reliably. Saves nothing."""
    reply = _parse(client, "preferences", PREFERENCES_SYSTEM_PROMPT, f"<description>{text}</description>",
                   ImprovedPreferences, config.PREFERENCES_TOKEN_CAP)
    if reply.parsed is None:
        raise UnusableResponse(f"No rewrite in response (stop_reason={reply.stop_reason})", reply.usage)
    return reply.parsed.text.strip(), reply.usage

def describe_outfit(client: Client, context: list[dict], language: Language = DEFAULT_LANGUAGE) -> tuple[OutfitDescription, TokenUsage]:
    """Name and explain an outfit the user put together. Saves nothing."""
    reply = _parse(client, "describe", describe_system_prompt(language), context, OutfitDescription, config.DESCRIBE_TOKEN_CAP)
    if reply.parsed is None:
        raise UnusableResponse(f"No description in response (stop_reason={reply.stop_reason})", reply.usage)
    return reply.parsed, reply.usage


def recommend_outfits(client: Client, context: list[dict], language: Language = DEFAULT_LANGUAGE) -> tuple[OutfitResult, TokenUsage]:
    return _outfit_style_call(client, context, language, OutfitResult, "outfits")


def weigh_candidate(client: Client, context: list[dict], language: Language = DEFAULT_LANGUAGE) -> tuple[WeighResult, TokenUsage]:
    """The weigh call: the outfit system prompt, the weigh instructions in the message, and a verdict plus outfits back."""
    return _outfit_style_call(client, context, language, WeighResult, "verdict")


def match_look(client: Client, context: list[dict], language: Language = DEFAULT_LANGUAGE) -> tuple[MimicResult, TokenUsage]:
    """mimic, step 2: text only. The look's tagged pieces against the cached wardrobe, and up to two recreations back."""
    return _outfit_style_call(client, context, language, MimicResult, "recreation")


def _outfit_style_call[T](client: Client, context: list[dict], language: Language, output_format: type[T], what: str) -> tuple[T, TokenUsage]:
    """One structured call with the outfit system prompt, on the outfits model. Outfits and weigh share it, so the
    outfit rules (coordination, weather, tiers) apply to the outfits weigh builds too."""
    reply = _parse(client, "outfits", outfit_system_prompt(language), context, output_format, config.OUTFIT_TOKEN_CAP)
    if reply.cut_off:
        logger.warning("%s response cut off at max_tokens (%s)", what.capitalize(), config.OUTFIT_TOKEN_CAP)
    if reply.parsed is None:
        raise UnusableResponse(f"No {what} in response (stop_reason={reply.stop_reason})", reply.usage)
    return reply.parsed, reply.usage


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Any      # as the model sent them: usually a dict, but nothing guarantees it


@dataclass
class ToolResult:
    call_id: str        # the ToolCall.id this answers
    content: str
    is_error: bool


@dataclass
class InsightsTurn:
    text: str                   # the turn's text, joined. The answer, when there are no tool calls
    tool_calls: list[ToolCall]  # empty when the model is done
    usage: TokenUsage
    stop_reason: str | None


# The same tool in the Responses API's shape. Strict mode needs every object closed, and sql is already required.
OPENAI_RUN_SELECT_TOOL = {
    "type": "function",
    "name": RUN_SELECT_TOOL["name"],
    "description": RUN_SELECT_TOOL["description"],
    "parameters": {**RUN_SELECT_TOOL["input_schema"], "additionalProperties": False},
    "strict": True,
}


class InsightsChat:
    """One "Ask your wardrobe" question, kept in the provider's own message format. insights.py runs the loop and
    the tools; this only builds the messages and makes the calls."""

    def __init__(self, client: Client, history: list[dict], question: str, language: Language = DEFAULT_LANGUAGE, preferences: str | None = None):
        self._client = client
        self._system = insights_system_prompt(language, preferences)
        self._last_output: list = []
        if client.provider == "openai":
            question_part = {"type": "input_text", "text": question}
            self._messages: list = [*history, {"role": "user", "content": [question_part]}]
            _add_breakpoint(question_part)
        else:
            self._messages = [*history, {"role": "user", "content": question}]

    def next_turn(self) -> InsightsTurn:
        model = model_for(self._client.provider, "insights")
        if self._client.provider == "openai":
            return self._openai_turn(model)
        with _service_errors():
            response = self._client.sdk.messages.create(
                model=model,
                max_tokens=anthropic_token_cap(model, config.INSIGHTS_TOKEN_CAP),
                system=self._system,
                tools=[RUN_SELECT_TOOL],
                cache_control={"type": "ephemeral"},
                messages=self._messages,
            )

        usage = _usage(model, response.usage)
        logger.debug("tokens: in=%s out=%s cache_creation=%s cache_read=%s", usage.input_tokens, usage.output_tokens, usage.cache_creation_input_tokens, usage.cache_read_input_tokens)
        logger.debug("blocks: %s", [block.type for block in response.content])
        if response.stop_reason == "max_tokens":
            logger.warning("Insights response cut off at max_tokens (%s)", anthropic_token_cap(model, config.INSIGHTS_TOKEN_CAP))

        self._last_output = response.content
        calls = []
        if response.stop_reason == "tool_use":
            calls = [ToolCall(block.id, block.name, block.input) for block in response.content if block.type == "tool_use"]
        text = "".join(block.text for block in response.content if block.type == "text")
        return InsightsTurn(text=text, tool_calls=calls, usage=usage, stop_reason=response.stop_reason)

    def add_tool_results(self, results: list[ToolResult]) -> None:
        """Answer the last turn's tool calls, ready for the next turn."""
        if self._client.provider == "openai":
            self._add_openai_results(results)
            return
        self._messages.append({"role": "assistant", "content": self._last_output})
        self._messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": result.call_id, "content": result.content, "is_error": result.is_error}
            for result in results
        ]})

    def _openai_turn(self, model: str) -> InsightsTurn:
        with _service_errors():
            response = self._client.sdk.responses.create(
                model=model,
                instructions=self._system,
                input=self._messages,
                tools=[OPENAI_RUN_SELECT_TOOL],
                max_output_tokens=config.INSIGHTS_TOKEN_CAP + config.OPENAI_REASONING_ALLOWANCE,
                reasoning={"effort": config.OPENAI_REASONING_EFFORT["insights"]},
                prompt_cache_options={"mode": "explicit"},
                store=False,
            )

        usage = _openai_usage(model, response.usage)
        logger.debug("tokens: in=%s out=%s cache_creation=%s cache_read=%s", usage.input_tokens, usage.output_tokens, usage.cache_creation_input_tokens, usage.cache_read_input_tokens)
        logger.debug("items: %s", [item.type for item in response.output])
        incomplete = response.incomplete_details.reason if response.incomplete_details else None
        if incomplete == "max_output_tokens":
            logger.warning("Insights response cut off at max_output_tokens (%s)", config.INSIGHTS_TOKEN_CAP + config.OPENAI_REASONING_ALLOWANCE)

        # With store=False nothing is kept server-side, so every item goes back next turn, reasoning included.
        self._last_output = list(response.output)
        calls = []
        if not incomplete:   # as on Anthropic, a reply cut off mid tool call is the answer, not a call to run
            calls = [ToolCall(item.call_id, item.name, _tool_arguments(item.arguments))
                     for item in response.output if item.type == "function_call"]
        text, refused = _openai_answer(response)
        stop_reason = incomplete or ("refusal" if refused else response.status)
        return InsightsTurn(text="" if refused else text, tool_calls=calls, usage=usage, stop_reason=stop_reason)

    def _add_openai_results(self, results: list[ToolResult]) -> None:
        self._messages.extend(self._last_output)
        last_part = None
        for result in results:
            # The Responses API has no is_error flag, so an error says so in its text.
            last_part = {"type": "input_text", "text": f"Error: {result.content}" if result.is_error else result.content}
            self._messages.append({"type": "function_call_output", "call_id": result.call_id, "output": [last_part]})
        if last_part:
            _add_breakpoint(last_part)


def _add_breakpoint(part: dict) -> None:
    """A cache breakpoint at the end of each turn's new content, and the earlier ones kept: OpenAI only matches the
    cache at breakpoints in the request, so the last turn's is where this turn reads the conversation so far. A
    question has at most INSIGHTS_MAX_TURNS of them; OpenAI looks at the latest 80."""
    part["prompt_cache_breakpoint"] = {"mode": "explicit"}


def _tool_arguments(arguments: str) -> Any:
    """The call's arguments as a dict. Text that isn't JSON comes back as is, and insights reports it as an error."""
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        return arguments

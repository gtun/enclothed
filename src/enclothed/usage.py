"""Token use and estimated cost, read from the LLM call logs.

This is the only code that reads the logs for usage, so moving to a DB table later changes one file.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from enclothed.config import DEFAULT_USER_ID, MODEL_PRICES
from enclothed.models import TokenUsage, UsageCall

logger = logging.getLogger(__name__)

TOKENS_PER_PRICE_UNIT = 1_000_000


def call_cost(usage: TokenUsage) -> float | None:
    """Estimated dollars for one call, or None when its model isn't in MODEL_PRICES."""
    price = MODEL_PRICES.get(usage.model)
    if price is None:
        return None
    total = (usage.input_tokens * price["input"]
             + usage.output_tokens * price["output"]
             + usage.cache_creation_input_tokens * price["cache_write"]
             + usage.cache_read_input_tokens * price["cache_read"])
    return total / TOKENS_PER_PRICE_UNIT


def _as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def _to_call(kind: str, entry: dict) -> UsageCall | None:
    """One log line as a call. None for test-mode lines, which have no usage."""
    if not entry.get("usage"):
        return None
    usage = TokenUsage.model_validate(entry["usage"])
    return UsageCall(
        timestamp=_as_utc(datetime.fromisoformat(entry["timestamp"])).isoformat(),
        # Lines from before accounts have no user_id. There was one user then.
        user_id=entry.get("user_id") or DEFAULT_USER_ID,
        kind=kind,
        model=usage.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_write_tokens=usage.cache_creation_input_tokens,
        cache_read_tokens=usage.cache_read_input_tokens,
        cost_usd=call_cost(usage),
    )


def _read_log(kind: str, path: Path) -> list[UsageCall]:
    if not path.exists():
        return []
    calls = []
    with path.open(encoding="utf-8") as log:
        for number, line in enumerate(log, start=1):
            try:
                call = _to_call(kind, json.loads(line))
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                logger.warning("Skipping %s line %d: %s", path.name, number, error)
                continue
            if call:
                calls.append(call)
    return calls


def read_calls(logs: dict[str, Path], start: datetime | None = None, end: datetime | None = None) -> list[UsageCall]:
    """Every logged LLM call from start up to (not including) end, oldest first. logs maps kind to file."""
    calls = [call for kind, path in logs.items() for call in _read_log(kind, path)]
    if start:
        calls = [c for c in calls if datetime.fromisoformat(c.timestamp) >= _as_utc(start)]
    if end:
        calls = [c for c in calls if datetime.fromisoformat(c.timestamp) < _as_utc(end)]
    return sorted(calls, key=lambda c: c.timestamp)


def log_failed_call(log_path: Path, user_id: int, usage: TokenUsage | None, error: str, request_id: str | None = None) -> None:
    """Record a call that failed. With usage, tokens were spent on an unusable answer, so the cost still shows.
    Without it, the API refused or never answered: nothing was billed, but the failure is on record."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_id": user_id,
        "usage": usage.model_dump() if usage else None,
        "error": error,
    }
    if request_id:
        entry["request_id"] = request_id   # what Anthropic support asks for
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

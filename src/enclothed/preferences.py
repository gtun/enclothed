"""Rewriting a person's style preferences into a clear brief for the outfit LLM. Saving them is db.save_preferences."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from enclothed.llm import Client, UnusableResponse, improve_preferences
from enclothed.usage import log_failed_call

logger = logging.getLogger(__name__)


def rewrite(client: Client, log_path: Path, user_id: int, text: str) -> str:
    """The rewrite, which saves nothing. The call goes in log_path, with its tokens, whether or not it was usable."""
    try:
        rewritten, usage = improve_preferences(client, text)
    except UnusableResponse as error:
        log_failed_call(log_path, user_id, error.usage, str(error))
        raise
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "user_id": user_id,
             "usage": usage.model_dump(), "input": text, "output": rewritten}
    with log_path.open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return rewritten

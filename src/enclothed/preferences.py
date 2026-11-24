"""Rewriting a person's style preferences into a clear brief for the outfit LLM. Saving them is db.save_preferences."""
import logging
from pathlib import Path

from enclothed.llm import Client, UnusableResponse, improve_preferences
from enclothed.usage import log_failed_call, write_entry

logger = logging.getLogger(__name__)


def rewrite(client: Client, log_path: Path, user_id: int, text: str) -> str:
    """The rewrite, which saves nothing. The call goes in log_path, with its tokens, whether or not it was usable."""
    try:
        rewritten, usage = improve_preferences(client, text)
    except UnusableResponse as error:
        log_failed_call(log_path, user_id, error.usage, str(error))
        raise
    write_entry(log_path, user_id, usage=usage.model_dump(), input=text, output=rewritten)
    return rewritten

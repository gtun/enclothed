"""Mend: ask the LLM for a garment's blank fields, from its saved photos and record. It only
ever fills blanks. The web app reviews the answers first, and the CLI saves them directly."""
import json
import logging
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import anthropic
from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from enclothed import config, db, photos
from enclothed.llm import UnusableResponse, fill_blanks
from enclothed.models import DEFAULT_LANGUAGE, Garment, Language, TokenUsage, blank_fields
from enclothed.usage import call_cost, log_failed_call

logger = logging.getLogger(__name__)

# Never sent. notes are the owner's private notes, and the rest mean nothing to the LLM.
NOT_SENT = {"id", "notes", "date_added", "set_id", "disowned_on", "mended_on", "user_id"}
SENDABLE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FAILURES_IN_A_ROW = 3


class NoPhotos(ValueError):
    """There's nothing to look at, so asking the LLM would be a guess."""


class Mended(BaseModel):
    filled: dict
    unanswered: list[str]
    usage: TokenUsage


def _sendable(paths: list[Path], tmp_dir: Path) -> list[Path]:
    """Older photos came straight from a camera. Shrink any the API would refuse."""
    ready = []
    for index, path in enumerate(paths):
        if path.suffix.lower() in SENDABLE_SUFFIXES and path.stat().st_size <= config.MEND_MAX_PHOTO_BYTES:
            ready.append(path)
        else:
            smaller = tmp_dir / f"{index:02d}.jpg"
            photos.normalize_photo(path, smaller)
            ready.append(smaller)
    return ready


def usable_answers(garment: Garment, answers: dict) -> dict:
    """Keep answers that fill a blank field with a valid value, whatever else the LLM sent."""
    blanks = blank_fields(garment)
    usable = {}
    for field, value in answers.items():
        if field not in blanks or value in (None, "", []):
            continue
        try:
            checked = Garment.model_validate({**garment.model_dump(), field: value})
        except ValidationError:
            logger.warning("Mend: dropped an invalid %s", field)
            continue
        usable[field] = checked.model_dump(mode="json")[field]
    return usable


def log_mend(log_path: Path, user_id: int, garment_id: int, usage: TokenUsage, filled: dict, unanswered: list[str]) -> None:
    """Goes in the tagging log, so it shows up with tagging on the usage page."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_id": user_id,
        "garment_id": garment_id,
        "mend": True,
        "usage": usage.model_dump(),
        "result": filled,
        "unanswered": unanswered,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def mend_garment(db_path: Path, log_path: Path, user_id: int, garment: Garment, client: Anthropic,
                 language: Language = DEFAULT_LANGUAGE, preferences: str | None = None) -> Mended:
    """Ask for the blank fields and return the answers. Only records that it asked; saves no answers."""
    blanks = blank_fields(garment)
    photo_paths = photos.get_photo_paths(garment.id)
    if not photo_paths:
        raise NoPhotos(f"Garment {garment.id} has no photos.")

    record = garment.model_dump(mode="json", exclude=NOT_SENT, exclude_none=True)
    with tempfile.TemporaryDirectory(prefix="mend-") as tmp:
        ready = _sendable(photo_paths, Path(tmp))
        try:
            answers, usage = fill_blanks(client, ready, record, blanks, language, preferences)
        except UnusableResponse as error:
            log_failed_call(log_path, user_id, error.usage, str(error))
            raise

    filled = usable_answers(garment, answers)
    unanswered = [field for field in blanks if field not in filled]
    db.set_mended_on(db_path, user_id, garment.id, date.today())
    log_mend(log_path, user_id, garment.id, usage, filled, unanswered)
    return Mended(filled=filled, unanswered=unanswered, usage=usage)


def garments_to_mend(db_path: Path, user_id: int, ids: list[int] | None = None, retry: bool = False) -> list[Garment]:
    """Owned garments with something blank. Ones already asked about are skipped, unless named or retrying."""
    garments = [g for g in db.select_owned_garments(db_path, user_id) if blank_fields(g)]
    if ids:
        return [g for g in garments if g.id in ids]
    return garments if retry else [g for g in garments if g.mended_on is None]


def mend_all(db_path: Path, log_path: Path, user_id: int, client: Anthropic, ids: list[int] | None = None, limit: int | None = None,
             retry: bool = False, language: Language = DEFAULT_LANGUAGE, preferences: str | None = None) -> int:
    """Mend and save, with no review. Returns how many garments failed."""
    waiting = garments_to_mend(db_path, user_id, ids, retry)
    garments = waiting[:limit] if limit else waiting
    print(f"Mending {len(garments)} of {len(waiting)} garments with blank fields.")

    cost, failures, in_a_row = 0.0, 0, 0
    for number, garment in enumerate(garments, start=1):
        label = f"[{number}/{len(garments)}] #{garment.id} {garment.name}"
        try:
            result = mend_garment(db_path, log_path, user_id, garment, client, language, preferences)
        except NoPhotos:
            print(f"{label}: skipped, no photos")
            continue
        except (anthropic.APIError, UnusableResponse, OSError, ValueError) as error:
            failures += 1
            in_a_row += 1
            print(f"{label}: FAILED, {error}")
            if in_a_row >= MAX_FAILURES_IN_A_ROW:
                print(f"Stopping after {in_a_row} failures in a row. Run it again to pick up where this left off.")
                break
            continue

        in_a_row = 0
        cost += call_cost(result.usage) or 0
        fresh = db.select_garment(db_path, user_id, garment.id)   # includes the mended_on just set
        db.update_garment(db_path, user_id, Garment.model_validate({**fresh.model_dump(), **result.filled}))
        filled = ", ".join(f"{field}={value}" for field, value in result.filled.items()) or "nothing"
        print(f"{label}: filled {filled}")
        if result.unanswered:
            print(f"    still blank: {', '.join(result.unanswered)}")

    print(f"Done. Estimated cost: ${cost:.2f}. Failed: {failures}.")
    return failures

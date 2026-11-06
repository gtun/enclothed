"""Tagged garments waiting for review. A draft is a folder of photos plus draft.json, kept
apart from the wardrobe, so nothing reaches outfits or Ask until its owner accepts it."""
import json
import logging
import re
import shutil
import time
from pathlib import Path
from uuid import uuid4

from anthropic import Anthropic

from enclothed import config
from enclothed.db import insert_garment
from enclothed.intake import file_photos, log_tagging, tag_photos
from enclothed.models import Draft, Garment, Language, TaggingResult

logger = logging.getLogger(__name__)

DRAFT_ID = re.compile(r"[0-9a-f]{32}")
DRAFT_FILE = "draft.json"


def _folder(drafts_dir: Path, user_id: int, draft_id: str) -> Path | None:
    """A draft's folder, if the id is well formed and this user has one. Each user only sees their own."""
    if not DRAFT_ID.fullmatch(draft_id):
        return None
    folder = drafts_dir / str(user_id) / draft_id
    return folder if (folder / DRAFT_FILE).is_file() else None


def remove_old_drafts(drafts_dir: Path) -> None:
    """Clear drafts nobody came back to, such as when a browser closed during review."""
    cutoff = time.time() - config.DRAFT_MAX_AGE_SECONDS
    for folder in drafts_dir.glob("*/*"):
        if folder.is_dir() and folder.stat().st_mtime < cutoff:
            logger.info("Removing abandoned draft %s", folder.name)
            shutil.rmtree(folder, ignore_errors=True)


def create_draft(drafts_dir: Path, user_id: int, photo_paths: list[Path], logging_path: Path, client: Anthropic | None,
                 prompt_message: str | None, notes: str | None, language: Language, preferences: str | None) -> Draft:
    remove_old_drafts(drafts_dir)
    wrapper, usage = tag_photos(user_id, photo_paths, logging_path, client, False, prompt_message, language, preferences)
    wrapper.garment.notes = notes

    draft = Draft(id=uuid4().hex, garment=wrapper.garment, photos=wrapper.photos)
    folder = drafts_dir / str(user_id) / draft.id
    folder.mkdir(parents=True)
    for path in photo_paths:
        shutil.move(path, folder / path.name)
    (folder / DRAFT_FILE).write_text(draft.model_dump_json(), encoding="utf-8")

    # Logged now, because the tokens are spent even if the owner discards this.
    log_tagging(logging_path, user_id, None, wrapper, usage, prompt_message, draft.id)
    return draft


def confirm_draft(drafts_dir: Path, db_path: Path, garments_path: Path, logging_path: Path, user_id: int, draft_id: str, garment: Garment) -> int | None:
    """Add the reviewed garment to the wardrobe. None if there's no such draft."""
    folder = _folder(drafts_dir, user_id, draft_id)
    if folder is None:
        return None

    draft = Draft.model_validate(json.loads((folder / DRAFT_FILE).read_text(encoding="utf-8")))
    reviewed = garment.model_copy(update={"id": None, "date_added": None, "set_id": None, "disowned_on": None, "mended_on": None, "user_id": None})
    garment_id = insert_garment(db_path, user_id, reviewed)

    photos = sorted(path for path in folder.iterdir() if path.name != DRAFT_FILE)
    file_photos(photos, draft.photos, garments_path / str(garment_id))
    shutil.rmtree(folder, ignore_errors=True)

    # No usage on this line, so the tagging call counts once. It ties the draft to its garment.
    log_tagging(logging_path, user_id, garment_id, TaggingResult(garment=reviewed, photos=draft.photos), None, None, draft_id)
    return garment_id


def discard_draft(drafts_dir: Path, user_id: int, draft_id: str) -> bool:
    folder = _folder(drafts_dir, user_id, draft_id)
    if folder is None:
        return False
    shutil.rmtree(folder, ignore_errors=True)
    return True

"""Rework (#74): see a change to one of your garments, such as "make it bright blue", as an edited copy of its photo.

Only the photo and the instruction go to the image model: nothing from the garment's record. The edited image is
saved as REWORKS_DIR/<id>.jpg, apart from the garment's photos, so it's never mistaken for one.
"""
import io
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from enclothed import config, db, photos
from enclothed.llm import Client, UnusableResponse, preview_garment
from enclothed.models import ImageUsage

logger = logging.getLogger(__name__)

JPEG_QUALITY = 90


class NoPhotos(ValueError):
    """The garment has no photo to edit."""


def source_photo(paths: list[Path]) -> Path:
    """The front photo, which shows the whole garment, or the first photo when there's no front one."""
    fronts = [p for p in paths if p.name.split("_")[0] == "front"]
    return fronts[0] if fronts else paths[0]


def image_path(reworks_dir: Path, rework_id: int) -> Path:
    return reworks_dir / f"{rework_id}.jpg"


def _as_jpeg(image: bytes) -> bytes:
    """The model sends PNG, several MB at this size. JPEG is a fraction of that and looks the same on a phone."""
    with Image.open(io.BytesIO(image)) as picture:
        out = io.BytesIO()
        picture.convert("RGB").save(out, "JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def log_call(log_path: Path, user_id: int, garment_id: int, usage: ImageUsage | None, rework_id: int | None = None,
             error: str | None = None) -> None:
    """One line per image call, kept apart from the token logs because its usage has a different shape. The
    instruction isn't logged: it's the person's own words, and the database already keeps it."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_id": user_id,
        "garment_id": garment_id,
        "rework_id": rework_id,
        "image_usage": usage.model_dump() if usage else None,
    }
    if error:
        entry["error"] = error
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def rework_garment(db_path: Path, reworks_dir: Path, log_path: Path, user_id: int, garment_id: int, instruction: str,
                   client: Client) -> dict:
    """Edit the garment's front photo by the instruction, save the result, and return its row. The caller has
    checked that the garment is this user's. ServiceError and UnusableResponse pass through, the latter logged."""
    paths = photos.get_photo_paths(garment_id)
    if not paths:
        raise NoPhotos(f"Garment {garment_id} has no photos.")
    source = source_photo(paths)
    with tempfile.TemporaryDirectory(prefix="rework-") as tmp:
        [sendable] = photos.sendable_copies([source], Path(tmp))
        try:
            image, usage = preview_garment(client, sendable, instruction)
        except UnusableResponse as error:
            log_call(log_path, user_id, garment_id, error.usage, error=str(error))
            raise

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rework_id = db.insert_rework(db_path, user_id, garment_id, instruction, source.name, usage.model, created_at)
    reworks_dir.mkdir(parents=True, exist_ok=True)
    try:
        image_path(reworks_dir, rework_id).write_bytes(_as_jpeg(image))
    except Exception:
        db.delete_rework(db_path, user_id, rework_id)   # a row with no image would show as broken
        log_call(log_path, user_id, garment_id, usage, error="Couldn't save the image")
        raise
    log_call(log_path, user_id, garment_id, usage, rework_id)
    return db.select_rework(db_path, user_id, rework_id)


def delete(db_path: Path, reworks_dir: Path, user_id: int, rework_id: int) -> bool:
    """Delete one of this user's reworks and its image. False if there's no such rework of theirs."""
    if not db.delete_rework(db_path, user_id, rework_id):
        return False
    image_path(reworks_dir, rework_id).unlink(missing_ok=True)
    return True


def remove_orphaned_files(db_path: Path, reworks_dir: Path) -> None:
    """Delete images whose rework is gone, as when its garment was deleted (the database removes the rows)."""
    if not reworks_dir.is_dir():
        return
    kept = db.select_rework_ids(db_path)
    for path in reworks_dir.glob("*.jpg"):
        if not (path.stem.isdigit() and int(path.stem) in kept):
            logger.info("Removing rework image %s: its rework is gone", path.name)
            path.unlink(missing_ok=True)

import logging
import shutil
import threading
from pathlib import Path
from typing import get_args

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from enclothed import config
from enclothed.config import THUMB_SIZE, UPLOAD_MAX_SIDE
from enclothed.models import LookPhoto, Photo, PhotoRole

register_heif_opener()  # lets Pillow open iPhone HEIC photos
logger = logging.getLogger(__name__)

# One thumbnail at a time. A page can ask for dozens at once, and the server has 1 GB of memory.
_thumbnail_lock = threading.Lock()

ROLES = get_args(PhotoRole)   # ("front", "back", "detail", "label", "other")
SENDABLE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def sendable_copies(paths: list[Path], tmp_dir: Path) -> list[Path]:
    """Saved photos to send to the LLM again (mend, the tagging eval). Older ones came straight from a camera, so
    any the API would refuse is shrunk into tmp_dir; the rest are sent as they are."""
    ready = []
    for index, path in enumerate(paths):
        if path.suffix.lower() in SENDABLE_SUFFIXES and path.stat().st_size <= config.MEND_MAX_PHOTO_BYTES:
            ready.append(path)
        else:
            smaller = tmp_dir / f"{index:02d}.jpg"
            normalize_photo(path, smaller)
            ready.append(smaller)
    return ready


def _photo_files(garment_id: int) -> list[Path]:
    photos_dir = config.GARMENTS_DIR / str(garment_id)
    if not photos_dir.is_dir():
        return []
    return [p for p in photos_dir.iterdir() if p.is_file() and not p.name.startswith(".")]


def get_garment_photos(garment_id: int) -> list[Photo]:
    photo_list = []
    for p in _photo_files(garment_id):
        prefix = p.name.split("_")[0]
        role = prefix if prefix in ROLES else "other"
        photo_list.append(Photo(
            role=role,
            url=f"/photos/{garment_id}/{p.name}",
            thumb_url=f"/thumbs/{garment_id}/{p.name}",
        ))

    photo_list.sort(key=lambda photo: (ROLES.index(photo.role), photo.url))

    return photo_list


def get_photo_paths(garment_id: int) -> list[Path]:
    return sorted(_photo_files(garment_id))


def _upright_rgb(image: Image.Image) -> Image.Image:
    """Apply the camera's rotation tag and drop transparency, so every output is a plain JPEG."""
    return ImageOps.exif_transpose(image).convert("RGB")


def get_photo(garment_id: int, filename: str) -> Path | None:
    """Path to one garment photo, or None if it doesn't exist or the name isn't a plain filename."""
    if Path(filename).name != filename or filename.startswith("."):
        return None
    source = config.GARMENTS_DIR / str(garment_id) / filename
    return source if source.is_file() else None


def _is_current(thumb: Path, source: Path) -> bool:
    return thumb.is_file() and thumb.stat().st_mtime >= source.stat().st_mtime


def get_thumbnail(garment_id: int, filename: str) -> Path | None:
    """Path to a small JPEG of one garment photo, made on first request and cached.

    Returns None when the photo doesn't exist. Rebuilt when the photo is newer than its thumbnail.
    """
    source = get_photo(garment_id, filename)
    if source is None:
        return None
    return _thumbnail(source, config.THUMBS_DIR / str(garment_id) / f"{filename}.jpg")


def _thumbnail(source: Path, thumb: Path) -> Path:
    """thumb, made from source if it's missing or older. The source itself if it can't be shrunk."""
    if _is_current(thumb, source):
        return thumb

    with _thumbnail_lock:
        if _is_current(thumb, source):   # another request for the same photo made it while this one waited
            return thumb
        thumb.parent.mkdir(parents=True, exist_ok=True)
        partial = thumb.with_name(thumb.name + ".partial")
        try:
            with Image.open(source) as image:
                # For a JPEG, decode at about the final size instead of loading every pixel.
                image.draft("RGB", (max(THUMB_SIZE), max(THUMB_SIZE)))
                small = _upright_rgb(image)
                small.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
                small.save(partial, "JPEG", quality=82, optimize=True)
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
            logger.warning("Couldn't make a thumbnail of %s; serving the original", source)
            partial.unlink(missing_ok=True)
            return source
        partial.replace(thumb)  # atomic, so a half-written file is never served
    return thumb


# --- looks to recreate (mimic, #5): one folder of photos per look, apart from the garments ---------
def save_look_photos(look_id: int, staged: list[Path]) -> None:
    """Move a look's normalized photos into its folder, keeping their order."""
    folder = config.LOOKS_DIR / str(look_id)
    folder.mkdir(parents=True, exist_ok=True)
    for index, path in enumerate(staged):
        shutil.move(path, folder / f"{index:02d}.jpg")


def get_look_photos(look_id: int) -> list[LookPhoto]:
    folder = config.LOOKS_DIR / str(look_id)
    if not folder.is_dir():
        return []
    names = sorted(p.name for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))
    return [LookPhoto(url=f"/looks/{look_id}/{name}", thumb_url=f"/looks/{look_id}/thumbs/{name}") for name in names]


def get_look_photo(look_id: int, filename: str) -> Path | None:
    """Path to one photo of a look, or None if it doesn't exist or the name isn't a plain filename."""
    if Path(filename).name != filename or filename.startswith("."):
        return None
    source = config.LOOKS_DIR / str(look_id) / filename
    return source if source.is_file() else None


def get_look_thumbnail(look_id: int, filename: str) -> Path | None:
    source = get_look_photo(look_id, filename)
    if source is None:
        return None
    return _thumbnail(source, config.THUMBS_DIR / "looks" / str(look_id) / f"{filename}.jpg")


def delete_garment_photos(garment_id: int) -> None:
    """A garment's photos and their thumbnails, for a garment that's gone from the database."""
    shutil.rmtree(config.GARMENTS_DIR / str(garment_id), ignore_errors=True)
    shutil.rmtree(config.THUMBS_DIR / str(garment_id), ignore_errors=True)


def delete_look_photos(look_id: int) -> None:
    shutil.rmtree(config.LOOKS_DIR / str(look_id), ignore_errors=True)
    shutil.rmtree(config.THUMBS_DIR / "looks" / str(look_id), ignore_errors=True)


def normalize_photo(source: Path, dest: Path) -> None:
    """Save an uploaded photo as an upright JPEG no larger than UPLOAD_MAX_SIDE.

    Keeps phone photos under the API's per-image size limit and converts HEIC.
    Raises ValueError when the file isn't an image Pillow can read.
    """
    try:
        with Image.open(source) as image:
            out = _upright_rgb(image)
    except (UnidentifiedImageError, Image.DecompressionBombError) as error:
        raise ValueError(f"{source.name} is not a readable image") from error
    out.thumbnail((UPLOAD_MAX_SIDE, UPLOAD_MAX_SIDE), Image.Resampling.LANCZOS)
    out.save(dest, "JPEG", quality=85, optimize=True)


def copy_without_metadata(source: Path, dest: Path, size: tuple[int, int]) -> bool:
    """Save an upright JPEG copy of source, no larger than size, for a share link.

    Pillow writes no EXIF unless asked, so the copy carries no camera, time or place: an old photo
    added from the CLI could still have its phone's GPS tag. One at a time, like thumbnails, because
    the server has 1 GB of memory. False when the photo can't be read, so the share leaves it out.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _thumbnail_lock:
        try:
            with Image.open(source) as image:
                image.draft("RGB", size)   # a JPEG decodes at about the final size
                out = _upright_rgb(image)
                out.thumbnail(size, Image.Resampling.LANCZOS)
                out.save(dest, "JPEG", quality=82, optimize=True)
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
            logger.warning("Couldn't copy %s for a share; leaving it out", source)
            dest.unlink(missing_ok=True)
            return False
    return True

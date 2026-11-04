import logging
from pathlib import Path
from typing import get_args

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from enclothed.config import GARMENTS_DIR, THUMBS_DIR, THUMB_SIZE, UPLOAD_MAX_SIDE
from enclothed.models import Photo, PhotoRole, User

register_heif_opener()  # lets Pillow open iPhone HEIC photos
logger = logging.getLogger(__name__)

ROLES = get_args(PhotoRole)   # ("front", "back", "detail", "label", "other")


def get_garment_photos(garment_id: int) -> list[Photo]:
    photos_dir = GARMENTS_DIR / str(garment_id)
    if not photos_dir.is_dir():
        return []
    photos = [p for p in photos_dir.iterdir() if p.is_file() and not p.name.startswith(".")]

    photo_list = []
    for p in photos:
        prefix = p.name.split("_")[0]
        role = prefix if prefix in ROLES else "other"
        photo_list.append(Photo(
            role=role,
            url=f"/photos/{garment_id}/{p.name}",
            thumb_url=f"/thumbs/{garment_id}/{p.name}",
        ))

    photo_list.sort(key=lambda photo: (ROLES.index(photo.role), photo.url))

    return photo_list


def _upright_rgb(image: Image.Image) -> Image.Image:
    """Apply the camera's rotation tag and drop transparency, so every output is a plain JPEG."""
    return ImageOps.exif_transpose(image).convert("RGB")


def get_thumbnail(garment_id: int, filename: str) -> Path | None:
    """Path to a small JPEG of one garment photo, made on first request and cached.

    Returns None when the photo doesn't exist. Rebuilt when the photo is newer than its thumbnail.
    """
    if Path(filename).name != filename or filename.startswith("."):
        return None
    source = GARMENTS_DIR / str(garment_id) / filename
    if not source.is_file():
        return None

    thumb = THUMBS_DIR / str(garment_id) / f"{filename}.jpg"
    if thumb.is_file() and thumb.stat().st_mtime >= source.stat().st_mtime:
        return thumb

    thumb.parent.mkdir(parents=True, exist_ok=True)
    partial = thumb.with_name(thumb.name + ".partial")
    try:
        with Image.open(source) as image:
            small = _upright_rgb(image)
            small.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
            small.save(partial, "JPEG", quality=82, optimize=True)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        logger.warning("Couldn't make a thumbnail of %s; serving the original", source)
        partial.unlink(missing_ok=True)
        return source
    partial.replace(thumb)  # atomic, so a half-written file is never served
    return thumb


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

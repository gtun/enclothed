"""Share links: a frozen copy of a garment, or of an outfit and its garments, that anyone with the link can see.

A share is a snapshot, taken when the link is made: later edits, disowning or deleting never change it, and
the shared page never reads the wardrobe. What it holds comes from the allow-lists below, so a field added to
garments or outfits later stays private until it's added here. Nothing in it says whose wardrobe it came from:
no usernames, no garment or outfit ids, no request wording, ratings or wears. Its photos are re-encoded copies,
which drops anything a camera stored in them, such as where the photo was taken.
"""
import logging
import secrets
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from enclothed import db, photos, responses
from enclothed.config import SHARE_LIFETIME_DAYS, SHARE_PHOTO_SIDE, THUMB_SIZE
from enclothed.models import Garment, Language

logger = logging.getLogger(__name__)

ShareKind = Literal["garment", "outfit"]

# What a shared garment page shows. Notes, styling notes, formality, fit and the rest stay private.
GARMENT_FIELDS = (
    "category", "subcategory", "brand", "primary_color", "secondary_colors", "accent_colors",
    "fabric_type", "materials", "country_of_origin", "style_tags",
)
# What a shared outfit page shows, besides its pieces. Left out: the request (prompt_message), the look it
# recreates (whose title came from the owner's photo), likes, wears and anchors (which garments were asked for).
OUTFIT_FIELDS = ("aesthetic", "explanation", "missing", "risk_tier", "timestamp")


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class ShareLimitReached(Exception):
    """This user already has as many live share links as they're allowed."""


class ShareAtMaxLifetime(Exception):
    """This link already expires SHARE_MAX_LIFETIME_DAYS after it was made, so it can't be extended."""


def new_token() -> str:
    """128 random bits, URL-safe: nobody finds a share by guessing."""
    return secrets.token_urlsafe(16)


def _copy_photos(garment_id: int, folder: Path) -> list[dict]:
    """Copies of a garment's photos, in the order its page shows them: {"role", "file"} for each one copied.
    Each is renamed by its role, since an original's file name could say anything."""
    copied = []
    for index, photo in enumerate(photos.get_garment_photos(garment_id)):
        source = photos.get_photo(garment_id, photo.url.rsplit("/", 1)[-1])
        if source is None:
            continue
        name = f"{photo.role}_{index:02d}.jpg"
        if photos.copy_without_metadata(source, folder / name, (SHARE_PHOTO_SIDE, SHARE_PHOTO_SIDE)) and \
           photos.copy_without_metadata(source, folder / "thumbs" / name, THUMB_SIZE):
            copied.append({"role": photo.role, "file": name})
    return copied


def _garment_snapshot(garment: Garment, folder: Path) -> dict:
    return {**garment.model_dump(mode="json", include=set(GARMENT_FIELDS)), "photos": _copy_photos(garment.id, folder)}


def _save(db_path: Path, shares_dir: Path, user_id: int, kind: ShareKind, language: Language, now: datetime,
          build, limit: int | None) -> tuple[str, str]:
    """Copy the photos and store the snapshot that build(folder) makes. If anything fails, nothing is left behind.
    With a limit, raises ShareLimitReached before copying anything if the user already has that many live links."""
    purge_expired(db_path, shares_dir, now)
    if limit is not None and len(db.select_user_shares(db_path, user_id, _iso(now))) >= limit:
        raise ShareLimitReached
    token = new_token()
    folder = shares_dir / token
    try:
        snapshot = {"kind": kind, "language": language, **build(folder)}
        expires_at = _iso(now + timedelta(days=SHARE_LIFETIME_DAYS))
        db.insert_share(db_path, token, user_id, kind, _iso(now), expires_at, snapshot)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    logger.info("Shared a %s, link expires %s", kind, expires_at)
    return token, expires_at


def share_garment(db_path: Path, shares_dir: Path, user_id: int, garment_id: int, language: Language,
                  now: datetime, limit: int | None = None) -> tuple[str, str] | None:
    """A new link to a copy of this garment: (token, expires_at), or None if it isn't this user's."""
    garment = db.select_garment(db_path, user_id, garment_id)
    if garment is None:
        return None
    return _save(db_path, shares_dir, user_id, "garment", language, now,
                 lambda folder: {"garment": _garment_snapshot(garment, folder / "0")}, limit)


def share_outfit(db_path: Path, shares_dir: Path, user_id: int, outfit_id: int, language: Language,
                 now: datetime, limit: int | None = None) -> tuple[str, str] | None:
    """A new link to a copy of this outfit and each of its garments: (token, expires_at), or None if it isn't this user's.
    Garments are numbered from 0 in the outfit's order; a piece names its garment by that number."""
    outfit = responses.get_outfit(db_path, user_id, outfit_id)
    if outfit is None:
        return None
    sets = db.select_all_sets(db_path, user_id)

    def build(folder: Path) -> dict:
        garments, pieces = [], []
        for index, entry in enumerate(outfit.garments):
            g = entry.garment
            garments.append(_garment_snapshot(g, folder / str(index)))
            pieces.append({"garment": index, "styling_advice": entry.styling_advice,
                           "in_set": g.set_id is not None, "set_name": sets.get(g.set_id) if g.set_id else None})
        return {"outfit": {**outfit.model_dump(mode="json", include=set(OUTFIT_FIELDS)), "pieces": pieces}, "garments": garments}

    return _save(db_path, shares_dir, user_id, "outfit", language, now, build, limit)


def load(db_path: Path, token: str, now: datetime) -> dict | None:
    """What the shared page shows, or None once the link has expired or never existed."""
    share = db.select_share(db_path, token, _iso(now))
    if share is None:
        return None
    return {**share.snapshot, "expires_at": share.expires_at}


def photo(db_path: Path, shares_dir: Path, token: str, garment: int, filename: str, small: bool, now: datetime) -> Path | None:
    """One of a live share's photo copies, or None. small gives the thumbnail."""
    if Path(filename).name != filename or filename.startswith(".") or db.select_share(db_path, token, _iso(now)) is None:
        return None
    path = shares_dir / token / str(garment) / ("thumbs" if small else "") / filename
    return path if path.is_file() else None


def revoke(db_path: Path, shares_dir: Path, user_id: int, token: str, now: datetime) -> bool:
    """End one of this user's live links now: its row, then its photo copies. False if it isn't theirs or
    isn't live. The token reaches the file system only after the database has matched it to a real share."""
    if not db.delete_share(db_path, token, user_id, _iso(now)):
        return False
    shutil.rmtree(shares_dir / token, ignore_errors=True)   # if this fails, start-up removes the orphaned folder
    logger.info("Revoked a share")
    return True


def extend(db_path: Path, user_id: int, token: str, now: datetime) -> str | None:
    """Make one of this user's live links last SHARE_LIFETIME_DAYS from now, but never past its maximum lifetime,
    and never shorter than it already is. Returns the new expiry, or None if it isn't theirs or isn't live.
    Raises ShareAtMaxLifetime if it already expires at its maximum."""
    share = db.select_user_share(db_path, token, user_id, _iso(now))
    if share is None:
        return None
    limit = responses.max_share_expiry(share.created_at)
    if share.expires_at >= limit:
        raise ShareAtMaxLifetime
    expires_at = max(share.expires_at, min(_iso(now + timedelta(days=SHARE_LIFETIME_DAYS)), limit))
    if not db.update_share_expiry(db_path, token, user_id, expires_at, _iso(now)):
        return None   # it expired or was revoked in between
    logger.info("Extended a share, link expires %s", expires_at)
    return expires_at


def purge_expired(db_path: Path, shares_dir: Path, now: datetime) -> None:
    """Delete expired shares and their photos."""
    for token in db.delete_expired_shares(db_path, _iso(now)):
        shutil.rmtree(shares_dir / token, ignore_errors=True)


def remove_orphaned_photos(db_path: Path, shares_dir: Path) -> None:
    """Delete photo folders with no share, such as one whose server stopped while it was being made.
    Only safe when no share is being made, so it runs when the server starts."""
    if not shares_dir.is_dir():
        return
    live = db.select_share_tokens(db_path)
    for folder in shares_dir.iterdir():
        if folder.name not in live:
            shutil.rmtree(folder, ignore_errors=True)

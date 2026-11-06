"""The shared demo wardrobe: a user anyone signed in can switch to, rebuilt every day.

`seed` copies a sample of the owner's wardrobe into a template, without private notes or the
words of past requests. `refresh` rebuilds the demo from that template once a day, so whatever
visitors add or change doesn't last. Only a user marked is_demo can be wiped: see
db.delete_demo_wardrobe.
"""
import json
import logging
import os
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import get_args

from enclothed import config, db, photos
from enclothed.models import Category, Garment, Outfit, OutfitGarment, User
from enclothed.usage import read_calls

logger = logging.getLogger(__name__)

TEMPLATE_FILE = "template.json"
PRIVATE_FIELDS = {"id", "notes", "set_id", "user_id", "date_added", "disowned_on"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def last_reset_time(now: datetime) -> datetime:
    """The most recent daily reset moment. The token limit starts over at the same moment."""
    today = now.replace(hour=config.DEMO_RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    return today if today <= now else today - timedelta(days=1)


# --- choosing what goes in the template -------------------------------------------------
def _pick_outfits(outfits: list[dict], garments: dict[int, Garment], limit: int) -> list[dict]:
    """Outfits made only of usable garments, liked ones first, then newest. Disliked ones stay out."""
    usable = [o for o in outfits if o["liked"] != 0 and all(g["garment_id"] in garments for g in o["garments"])]
    return sorted(usable, key=lambda o: (o["liked"] == 1, o["id"]), reverse=True)[:limit]


def _top_up_category(chosen: set[int], garments: dict[int, Garment], category: str, target: int) -> None:
    """Add garments until the category has target, taking subcategories not yet shown first."""
    in_category = [g for g in garments.values() if g.category == category]
    have = [g for g in in_category if g.id in chosen]
    seen = defaultdict(int)
    for garment in have:
        seen[garment.subcategory] += 1
    remaining = [g for g in in_category if g.id not in chosen]
    while len(have) < target and remaining:
        pick = min(remaining, key=lambda g: (seen[g.subcategory], g.id))
        remaining.remove(pick)
        have.append(pick)
        seen[pick.subcategory] += 1
        chosen.add(pick.id)


def choose_sample(garments: list[Garment], outfits: list[dict], per_category: int, max_outfits: int) -> tuple[list[Garment], list[dict]]:
    """A mix across categories that includes every garment in the chosen outfits, and whole sets."""
    by_id = {g.id: g for g in garments}
    picked_outfits = _pick_outfits(outfits, by_id, max_outfits)
    chosen = {entry["garment_id"] for outfit in picked_outfits for entry in outfit["garments"]}
    for category in get_args(Category):
        _top_up_category(chosen, by_id, category, per_category)
    sets = {by_id[i].set_id for i in chosen} - {None}
    chosen |= {g.id for g in garments if g.set_id in sets}
    return [by_id[i] for i in sorted(chosen)], picked_outfits


def _has_photos(garment_id: int) -> bool:
    folder = photos.GARMENTS_DIR / str(garment_id)
    return folder.is_dir() and any(folder.iterdir())


def build_template(db_path: Path, owner_id: int, template_dir: Path, per_category: int, max_outfits: int) -> dict:
    """Write the template: the sample's text in a JSON file and its photos in folders."""
    garments = [g for g in db.select_owned_garments(db_path, owner_id) if _has_photos(g.id)]
    sample, outfits = choose_sample(garments, db.select_all_outfits(db_path, owner_id), per_category, max_outfits)
    set_names = db.select_all_sets(db_path, owner_id)

    sets = defaultdict(list)
    for garment in sample:
        if garment.set_id is not None:
            sets[garment.set_id].append(garment.id)

    template = {
        "garments": [{"source_id": g.id, "garment": g.model_dump(mode="json", exclude=PRIVATE_FIELDS)} for g in sample],
        "sets": [{"name": set_names.get(set_id), "garment_ids": ids} for set_id, ids in sets.items()],
        "outfits": [{
            "aesthetic": o["aesthetic"],
            "explanation": o["explanation"],
            "missing": o["missing"],
            "liked": o["liked"],
            "garments": o["garments"],
        } for o in outfits],
    }

    shutil.rmtree(template_dir, ignore_errors=True)
    (template_dir / "garments").mkdir(parents=True)
    for garment in sample:
        shutil.copytree(photos.GARMENTS_DIR / str(garment.id), template_dir / "garments" / str(garment.id))
    (template_dir / TEMPLATE_FILE).write_text(json.dumps(template, ensure_ascii=False, indent=1), encoding="utf-8")
    return template


# --- rebuilding the demo ----------------------------------------------------------------
def _set_aside_leftover_photos(garment_id: int, timestamp: str) -> None:
    """Move a photo folder out of the way when a new garment gets its id.

    SQLite reuses the highest id once its row is gone, but the row's photos can outlive it.
    These aren't the demo's, so they must not show up in it or be deleted by a reset.
    """
    folder = photos.GARMENTS_DIR / str(garment_id)
    if folder.exists():
        destination = photos.GARMENTS_DIR.parent / "orphaned-photos" / f"{garment_id}-{timestamp.replace(':', '')}"
        destination.parent.mkdir(exist_ok=True)
        logger.warning("Garment folder %s had no garment; moved it to %s", garment_id, destination)
        folder.rename(destination)


def reset_wardrobe(db_path: Path, demo_id: int, template_dir: Path, timestamp: str) -> None:
    """Put the demo wardrobe back to the template.

    The template's garments keep their ids and photo folders from day to day, because the NAS
    backup never deletes: a fresh set of folders every day would pile up there forever.
    Only what visitors added is removed.
    """
    template_path = template_dir / TEMPLATE_FILE
    template = json.loads(template_path.read_text(encoding="utf-8"))
    keep = {entry["demo_id"] for entry in template["garments"] if "demo_id" in entry}

    for garment_id in db.delete_demo_wardrobe(db_path, demo_id, keep):
        shutil.rmtree(photos.GARMENTS_DIR / str(garment_id), ignore_errors=True)
        shutil.rmtree(photos.THUMBS_DIR / str(garment_id), ignore_errors=True)
    db.save_preferences(db_path, demo_id, None, timestamp)

    new_ids = {}
    for entry in template["garments"]:
        if "demo_id" in entry:
            db.update_garment(db_path, demo_id, Garment.model_validate({**entry["garment"], "id": entry["demo_id"]}))
        else:
            entry["demo_id"] = db.insert_garment(db_path, demo_id, Garment.model_validate(entry["garment"]))
            _set_aside_leftover_photos(entry["demo_id"], timestamp)
            # Hard links: the same photos, without using the disk twice.
            shutil.copytree(template_dir / "garments" / str(entry["source_id"]), photos.GARMENTS_DIR / str(entry["demo_id"]), copy_function=os.link)
        new_ids[entry["source_id"]] = entry["demo_id"]
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=1), encoding="utf-8")

    for entry in template["sets"]:
        db.insert_set(db_path, demo_id, [new_ids[i] for i in entry["garment_ids"]], entry["name"])

    for entry in template["outfits"]:
        outfit = Outfit(
            aesthetic=entry["aesthetic"],
            explanation=entry["explanation"],
            missing=entry["missing"],
            garments=[OutfitGarment(garment_id=new_ids[g["garment_id"]], styling_advice=g["styling_advice"]) for g in entry["garments"]],
        )
        [outfit_id] = db.insert_outfits(db_path, demo_id, [outfit], None, config.DEMO_OUTFIT_REQUEST, timestamp)
        if entry["liked"] is not None:
            db.set_outfit_liked(db_path, demo_id, outfit_id, entry["liked"])


def refresh(db_path: Path, demo: User, now: datetime | None = None) -> None:
    """Rebuild the demo if it hasn't been since the last reset time. Called when someone opens it.

    Claiming the reset in the database first means two requests at once can't both rebuild.
    """
    now = now or _utc_now()
    cutoff = last_reset_time(now).isoformat()
    if demo.demo_reset_at and demo.demo_reset_at >= cutoff:
        return
    timestamp = now.isoformat(timespec="seconds")
    if not db.claim_demo_reset(db_path, demo.id, cutoff, timestamp):
        return
    logger.info("Resetting the demo wardrobe")
    try:
        reset_wardrobe(db_path, demo.id, config.DEMO_TEMPLATE_DIR, timestamp)
    except Exception:
        db.clear_demo_reset(db_path, demo.id)   # so the next request tries again
        raise


def seed(db_path: Path, owner_id: int, per_category: int, max_outfits: int) -> dict:
    """Build the template from the owner's wardrobe, create the demo user if needed, and fill it."""
    template = build_template(db_path, owner_id, config.DEMO_TEMPLATE_DIR, per_category, max_outfits)
    demo = db.select_demo_user(db_path)
    demo_id = demo.id if demo else db.insert_demo_user(db_path, config.DEMO_USERNAME)
    timestamp = _utc_now().isoformat(timespec="seconds")
    reset_wardrobe(db_path, demo_id, config.DEMO_TEMPLATE_DIR, timestamp)
    db.claim_demo_reset(db_path, demo_id, "9999", timestamp)
    return template


# --- the daily token limit --------------------------------------------------------------
def tokens_used(logs: dict[str, Path], demo_id: int, now: datetime | None = None) -> int:
    """Tokens the demo has spent since the last reset. Cache reads are nearly free, so they don't count."""
    since = last_reset_time(now or _utc_now())
    calls = [call for call in read_calls(logs, since) if call.user_id == demo_id]
    return sum(c.input_tokens + c.output_tokens + c.cache_write_tokens for c in calls)

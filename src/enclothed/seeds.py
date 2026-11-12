"""Load a synthetic wardrobe from seeds/ into a user's account, for testing outfits at scale.

The seeds are text only (scripts/make_demo_seeds.py writes them): the web app shows each garment
as a swatch of its primary color until it has photos. They use the same JSON shape as the demo
template, so a seed could later stand in for one.
"""
import json
import logging
from pathlib import Path

from enclothed import db
from enclothed.models import Garment

logger = logging.getLogger(__name__)


class SeedError(Exception):
    """A seed that can't be loaded as asked. Nothing has been written when this is raised."""


def read_seed(seed_path: Path) -> tuple[list[tuple[int, Garment]], list[dict]]:
    """Every garment validated before anything is written, so a bad row can't leave half a wardrobe."""
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    garments = []
    for entry in seed["garments"]:
        try:
            garments.append((entry["source_id"], Garment.model_validate(entry["garment"])))
        except ValueError as error:
            raise SeedError(f"Garment {entry.get('source_id')} in {seed_path.name} is invalid: {error}") from error
    known = {source_id for source_id, _ in garments}
    for kit in seed.get("sets", []):
        missing = set(kit["garment_ids"]) - known
        if missing:
            raise SeedError(f"Set {kit.get('name')!r} names garments not in the seed: {sorted(missing)}")
    return garments, seed.get("sets", [])


def load_seed(db_path: Path, user_id: int, seed_path: Path, allow_existing: bool = False) -> tuple[int, int]:
    """Add a seed's garments and sets to a user's wardrobe. Returns (garments, sets) added.

    Refuses a wardrobe that already has garments unless allow_existing: 300 rows landing in a real
    wardrobe by a typo in the user id would take a long time to clean up.
    """
    if db.select_user(db_path, user_id) is None:
        raise SeedError(f"No user {user_id}. Add one with `enclothed adduser` first.")
    existing = db.select_owned_garments(db_path, user_id)
    if existing and not allow_existing:
        raise SeedError(f"User {user_id} already has {len(existing)} garments. Pass --allow-existing to add to them anyway.")

    garments, sets = read_seed(seed_path)
    new_ids = {source_id: db.insert_garment(db_path, user_id, garment) for source_id, garment in garments}
    for kit in sets:
        db.insert_set(db_path, user_id, [new_ids[i] for i in kit["garment_ids"]], kit.get("name"))
    logger.info("Loaded %d garments and %d sets from %s into user %d", len(new_ids), len(sets), seed_path, user_id)
    return len(new_ids), len(sets)

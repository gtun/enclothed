"""Synthetic seed wardrobes: the shipped files are valid, and load-seed fills only the user asked for."""
import json
from collections import Counter
from pathlib import Path
from typing import get_args

import pytest

from enclothed import config, db, main, seeds
from enclothed.intake import TEST_GARMENT
from enclothed.models import Category

SEEDS_DIR = Path(__file__).parent.parent / "seeds"
SEED_FILES = sorted(SEEDS_DIR.glob("*.json"))
MENSWEAR_ONLY = {"suit jacket"}   # spot checks that the seeds stayed separate
WOMENSWEAR_ONLY = {"slip dress", "pumps", "camisole", "handbag"}


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    assert db.insert_user(path, "bob", "bob@example.com") == 2
    monkeypatch.setattr(config, "DB_PATH", path)
    return path


def write_seed(tmp_path, garments, sets=()):
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({"garments": garments, "sets": list(sets), "outfits": []}), encoding="utf-8")
    return path


def entry(source_id, **fields):
    garment = TEST_GARMENT.model_dump(mode="json", exclude_none=True)
    return {"source_id": source_id, "garment": {**garment, **fields}}


# --- the shipped seeds --------------------------------------------------------------
def test_both_seeds_ship():
    assert {p.stem for p in SEED_FILES} == {"menswear", "womenswear"}


@pytest.mark.parametrize("path", SEED_FILES, ids=lambda p: p.stem)
def test_seed_has_300_valid_garments_across_every_category(path):
    garments, sets = seeds.read_seed(path)
    assert len(garments) == 300
    assert len({source_id for source_id, _ in garments}) == 300
    counts = Counter(g.category for _, g in garments)
    assert set(counts) == set(get_args(Category))
    assert all(g.styling_notes for _, g in garments)
    assert sets, "each seed has at least one set"


@pytest.mark.parametrize("path", SEED_FILES, ids=lambda p: p.stem)
def test_seed_leaves_out_private_fields(path):
    seed = json.loads(path.read_text(encoding="utf-8"))
    private = {"id", "notes", "user_id", "set_id", "date_added", "disowned_on", "weighed_on", "mended_on"}
    assert all(not private & e["garment"].keys() for e in seed["garments"])


def test_seeds_keep_menswear_and_womenswear_apart():
    by_seed = {p.stem: {g.subcategory for _, g in seeds.read_seed(p)[0]} for p in SEED_FILES}
    assert not by_seed["menswear"] & WOMENSWEAR_ONLY
    assert by_seed["womenswear"] & WOMENSWEAR_ONLY == WOMENSWEAR_ONLY
    assert MENSWEAR_ONLY <= by_seed["menswear"]


# --- loading --------------------------------------------------------------------------
def test_load_seed_adds_garments_and_sets_to_that_user_only(tmp_path, db_path):
    path = write_seed(tmp_path, [entry(1, category="top", subcategory="t-shirt"), entry(2, category="top", subcategory="polo"),
                                  entry(3, category="bottom", subcategory="chinos")],
                      [{"name": "navy kit", "garment_ids": [1, 3]}])

    assert seeds.load_seed(db_path, 2, path) == (3, 1)

    bobs = db.select_owned_garments(db_path, 2)
    assert [g.subcategory for g in bobs] == ["t-shirt", "polo", "chinos"]
    assert bobs[0].set_id is not None and bobs[0].set_id == bobs[2].set_id and bobs[1].set_id is None
    assert db.select_owned_garments(db_path, 1) == []


def test_load_seed_refuses_a_wardrobe_with_garments(tmp_path, db_path):
    db.insert_garment(db_path, 2, TEST_GARMENT)
    path = write_seed(tmp_path, [entry(1)])

    with pytest.raises(seeds.SeedError, match="already has 1 garments"):
        seeds.load_seed(db_path, 2, path)
    assert len(db.select_owned_garments(db_path, 2)) == 1

    assert seeds.load_seed(db_path, 2, path, allow_existing=True) == (1, 0)
    assert len(db.select_owned_garments(db_path, 2)) == 2


def test_load_seed_refuses_a_missing_user(tmp_path, db_path):
    with pytest.raises(seeds.SeedError, match="No user 9"):
        seeds.load_seed(db_path, 9, write_seed(tmp_path, [entry(1)]))


def test_a_bad_row_writes_nothing(tmp_path, db_path):
    path = write_seed(tmp_path, [entry(1), entry(2, subcategory="pumps")])   # pumps are shoes, not outerwear

    with pytest.raises(seeds.SeedError, match="Garment 2"):
        seeds.load_seed(db_path, 2, path)
    assert db.select_owned_garments(db_path, 2) == []


def test_a_set_naming_a_missing_garment_writes_nothing(tmp_path, db_path):
    path = write_seed(tmp_path, [entry(1)], [{"name": "broken", "garment_ids": [1, 7]}])

    with pytest.raises(seeds.SeedError, match=r"\[7\]"):
        seeds.load_seed(db_path, 2, path)
    assert db.select_owned_garments(db_path, 2) == []


def test_load_seed_command(tmp_path, db_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["enclothed", "load-seed", str(SEEDS_DIR / "womenswear.json"), "-u", "2"])
    assert main.main() == 0
    assert "Added 300 garments" in capsys.readouterr().out
    assert len(db.select_owned_garments(db_path, 2)) == 300

    # A second run would double the wardrobe, so it stops with a usage error instead.
    with pytest.raises(SystemExit):
        main.main()
    assert len(db.select_owned_garments(db_path, 2)) == 300


def test_seed_garments_survive_a_round_trip(tmp_path, db_path):
    """What comes back from the database matches the seed, field for field."""
    path = SEEDS_DIR / "menswear.json"
    seeds.load_seed(db_path, 2, path)
    expected = [g for _, g in seeds.read_seed(path)[0]]
    stored = db.select_owned_garments(db_path, 2)
    ignore = {"id", "date_added", "set_id", "user_id"}
    assert [g.model_dump(exclude=ignore) for g in stored] == [g.model_dump(exclude=ignore) for g in expected]

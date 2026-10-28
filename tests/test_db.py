import sqlite3
from contextlib import closing

import pytest
from pydantic import ValidationError

from enclothed.db import init_db, insert_garment, insert_outfits, select_garment, DB_DEFAULT_FIELDS
from enclothed.models import Garment, Outfit
from enclothed.config import SCHEMA_PATH, MIGRATIONS_DIR
from enclothed.intake import TEST_GARMENT

@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    return path

def test_garment_matches_table(db_path):
    # 1. Columns according to SQLite
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("PRAGMA table_info(garments)").fetchall()

    table_columns = {col[1] for col in rows}
    model_fields = set(Garment.model_fields)

    only_in_model = model_fields - table_columns
    only_in_table = table_columns - model_fields

    assert not only_in_model, f"Fields with no column: {only_in_model}"
    assert not only_in_table, f"Columns with no field: {only_in_table}"

def test_insert_select_round_trip(db_path):
    garment_id = insert_garment(db_path, TEST_GARMENT)
    new_garment = select_garment(db_path, garment_id)

    assert new_garment is not None, f"Garment {garment_id} was not found"
    assert new_garment.id == garment_id
    assert TEST_GARMENT.model_dump(exclude=DB_DEFAULT_FIELDS) == new_garment.model_dump(exclude=DB_DEFAULT_FIELDS)

def test_select_missing_id_returns_none(db_path):
    new_garment = select_garment(db_path, -5)

    assert new_garment is None

def test_select_rejects_out_of_range_formality(db_path):
    garment_id = insert_garment(db_path, TEST_GARMENT)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("UPDATE garments SET formality=8 WHERE id = :id;", {"id":garment_id})

    with pytest.raises(ValidationError):
        select_garment(db_path, garment_id)

def test_select_rejects_null_accent_colors(db_path):
    garment_id = insert_garment(db_path, TEST_GARMENT)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("UPDATE garments SET accent_colors=NULL WHERE id = :id;", {"id":garment_id})

    with pytest.raises(ValidationError):
        select_garment(db_path, garment_id)


# --- insert_outfits -----------------------------------------------------------------
# outfit_garments has foreign keys to garments, so each test inserts real garments first.

TIMESTAMP = "2026-10-26T22:00:00+00:00"


@pytest.fixture
def garment_ids(db_path):
    """Three real garment rows; returns their ids."""
    return [insert_garment(db_path, TEST_GARMENT) for _ in range(3)]


def make_outfit(ids, aesthetic="test look", missing=None):
    return Outfit(
        aesthetic=aesthetic,
        explanation="why it works",
        missing=missing,
        garments=[{"garment_id": i, "styling_advice": f"advice {i}"} for i in ids],
    )


def rows(db_path, sql):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql).fetchall()]


def test_insert_outfits_returns_one_new_id_per_outfit(db_path, garment_ids):
    outfits = [make_outfit(garment_ids[:2]), make_outfit(garment_ids[1:])]
    new_ids = insert_outfits(db_path, outfits, None, "dinner", TIMESTAMP)
    assert len(new_ids) == 2
    assert len(set(new_ids)) == 2
    assert [r["id"] for r in rows(db_path, "SELECT id FROM outfits ORDER BY id")] == new_ids


def test_insert_outfits_writes_outfit_rows(db_path, garment_ids):
    outfits = [make_outfit(garment_ids, aesthetic="A"), make_outfit(garment_ids, aesthetic="B", missing="a belt")]
    insert_outfits(db_path, outfits, None, "dinner downtown", TIMESTAMP)
    saved = rows(db_path, "SELECT timestamp, prompt_message, aesthetic, explanation, missing, liked FROM outfits ORDER BY id")
    assert saved == [
        {"timestamp": TIMESTAMP, "prompt_message": "dinner downtown", "aesthetic": "A",
         "explanation": "why it works", "missing": None, "liked": None},
        {"timestamp": TIMESTAMP, "prompt_message": "dinner downtown", "aesthetic": "B",
         "explanation": "why it works", "missing": "a belt", "liked": None},
    ]


def test_insert_outfits_writes_garment_rows_with_advice(db_path, garment_ids):
    [outfit_id] = insert_outfits(db_path, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    saved = rows(db_path, "SELECT outfit_id, garment_id, styling_advice FROM outfit_garments ORDER BY garment_id")
    assert saved == [
        {"outfit_id": outfit_id, "garment_id": i, "styling_advice": f"advice {i}"} for i in garment_ids
    ]


def test_insert_outfits_marks_anchors(db_path, garment_ids):
    anchor = garment_ids[0]
    insert_outfits(db_path, [make_outfit(garment_ids)], [anchor], "dinner", TIMESTAMP)
    saved = rows(db_path, "SELECT garment_id, is_anchor FROM outfit_garments ORDER BY garment_id")
    assert saved == [{"garment_id": i, "is_anchor": 1 if i == anchor else 0} for i in garment_ids]


def test_insert_outfits_without_anchors_marks_none(db_path, garment_ids):
    insert_outfits(db_path, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    assert {r["is_anchor"] for r in rows(db_path, "SELECT is_anchor FROM outfit_garments")} == {0}


def test_insert_outfits_empty_list_writes_nothing(db_path):
    assert insert_outfits(db_path, [], None, "dinner", TIMESTAMP) == []
    assert rows(db_path, "SELECT * FROM outfits") == []


def test_insert_outfits_is_all_or_nothing(db_path, garment_ids):
    # The second outfit points at a garment that doesn't exist. The foreign key rejects it,
    # and the transaction must roll back the first outfit too: no half-saved replies.
    outfits = [make_outfit(garment_ids), make_outfit([garment_ids[0], 999])]
    with pytest.raises(sqlite3.IntegrityError):
        insert_outfits(db_path, outfits, None, "dinner", TIMESTAMP)
    assert rows(db_path, "SELECT * FROM outfits") == []
    assert rows(db_path, "SELECT * FROM outfit_garments") == []


# --- migrations ------------------------------------------------------------------
# The garments table as it was before migration 001, trimmed to the columns that matter.
OLD_GARMENTS_TABLE = """
CREATE TABLE garments (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL,
    wear_count INTEGER NOT NULL DEFAULT 0,
    last_worn TEXT
);
"""


def user_version(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def garment_columns(path):
    with closing(sqlite3.connect(path)) as conn:
        return {row[1] for row in conn.execute("PRAGMA table_info(garments)")}


def make_old_db(path):
    """A version-0 database with the old columns and two garments in it."""
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.executescript(OLD_GARMENTS_TABLE)
            conn.execute("INSERT INTO garments (category, wear_count) VALUES ('top', 3), ('shoes', 0)")


LATEST = max(int(p.name.split("_")[0]) for p in MIGRATIONS_DIR.glob("*.sql"))


def test_fresh_db_is_stamped_with_latest_version(db_path):
    assert user_version(db_path) == LATEST
    assert "wear_count" not in garment_columns(db_path)


def test_old_db_is_migrated_and_keeps_its_rows(tmp_path):
    path = tmp_path / "old.db"
    make_old_db(path)
    assert user_version(path) == 0

    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)

    assert user_version(path) == LATEST
    columns = garment_columns(path)
    # --- 001 migration -------------
    assert "wear_count" not in columns
    assert "last_worn" not in columns
    # --- 002 migration -------------
    assert "set_id" in columns
    # --- end migrations ------------
    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute("SELECT id, category FROM garments ORDER BY id").fetchall()
    assert rows == [(1, "top"), (2, "shoes")]


def test_init_db_twice_changes_nothing(tmp_path):
    path = tmp_path / "old.db"
    make_old_db(path)
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    columns_after_first = garment_columns(path)

    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)  # would raise "no such column" if 001 ran again

    assert user_version(path) == LATEST
    assert garment_columns(path) == columns_after_first


def test_failed_migration_rolls_back(tmp_path):
    # A copy of the real migrations plus a broken one whose first statement succeeds.
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    for source in MIGRATIONS_DIR.glob("*.sql"):
        (migrations / source.name).write_text(source.read_text())
    bad_number = LATEST + 1
    (migrations / f"{bad_number:03d}_broken.sql").write_text(
        "ALTER TABLE garments ADD COLUMN half_done TEXT;\n"
        "ALTER TABLE no_such_table ADD COLUMN x TEXT;\n"
    )
    path = tmp_path / "old.db"
    make_old_db(path)

    with pytest.raises(sqlite3.OperationalError):
        init_db(path, SCHEMA_PATH, migrations)

    # The good migrations committed; the broken one left no trace.
    assert user_version(path) == LATEST
    assert "half_done" not in garment_columns(path)

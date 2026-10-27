import sqlite3
from contextlib import closing

import pytest
from pydantic import ValidationError

from enclothed.db import init_db, insert_garment, insert_outfits, select_garment, DB_DEFAULT_FIELDS
from enclothed.models import Garment, Outfit
from enclothed.config import SCHEMA_PATH
from enclothed.intake import TEST_GARMENT

@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(path, SCHEMA_PATH)
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

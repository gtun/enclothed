import sqlite3
from contextlib import closing

import pytest

from wardrobe_ai.db import init_db, insert_garment, select_garment, DB_DEFAULT_FIELDS
from wardrobe_ai.models import Garment
from wardrobe_ai.config import SCHEMA_PATH
from wardrobe_ai.intake import TEST_GARMENT

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
    
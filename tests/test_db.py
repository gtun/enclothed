import sqlite3
from contextlib import closing

import pytest

from wardrobe_ai.db import init_db
from wardrobe_ai.models import Garment
from wardrobe_ai.config import SCHEMA_PATH

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
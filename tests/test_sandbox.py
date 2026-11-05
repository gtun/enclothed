import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from enclothed import config, db
from enclothed.sandbox import INSIGHTS_SCHEMA, build_snapshot

OWNER = 1    # schema.sql creates this user
OTHER = 2
DISOWNED_GARMENT = 3


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A real-schema database where each user owns one of everything, with ids matching the user's id."""
    path = tmp_path / "test.db"
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute("INSERT INTO users (id, username) VALUES (?, ?)", (OTHER, "other"))
            for user_id in (OWNER, OTHER):
                conn.execute("INSERT INTO sets (id, name, user_id) VALUES (?, 'suit', ?)", (user_id, user_id))
                conn.execute(
                    "INSERT INTO garments (id, category, subcategory, primary_color, styling_notes, notes, user_id) "
                    "VALUES (?, 'top', 'shirt', 'black', 'plain', 'private', ?)",
                    (user_id, user_id),
                )
                conn.execute(
                    "INSERT INTO outfits (id, timestamp, prompt_message, aesthetic, explanation, user_id) "
                    "VALUES (?, '2026-11-05T00:00:00+00:00', 'dinner', 'minimal', 'why', ?)",
                    (user_id, user_id),
                )
                conn.execute("INSERT INTO outfit_garments (outfit_id, garment_id) VALUES (?, ?)", (user_id, user_id))
                conn.execute(
                    "INSERT INTO wears (id, outfit_id, date, notes) VALUES (?, ?, '2026-11-05', 'private')",
                    (user_id, user_id),
                )
            conn.execute(
                "INSERT INTO garments (id, category, subcategory, primary_color, styling_notes, user_id, disowned_on) "
                "VALUES (?, 'top', 'shirt', 'white', 'plain', ?, '2026-11-01')",
                (DISOWNED_GARMENT, OWNER),
            )
    return path


@pytest.fixture
def snapshot(db_path: Path):
    """OWNER's copy, closed after each test."""
    with closing(build_snapshot(db_path, OWNER)) as conn:
        yield conn


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {name for (name,) in rows}


def values(conn: sqlite3.Connection, table: str, column: str) -> set:
    return {value for (value,) in conn.execute(f"SELECT {column} FROM {table}").fetchall()}


def test_every_table_is_copied(snapshot):
    assert table_names(snapshot) == set(INSIGHTS_SCHEMA)


@pytest.mark.parametrize("table", ["garments", "sets", "outfits"])
def test_only_the_owners_rows_are_copied(snapshot, table):
    ids = values(snapshot, table, "id")
    assert OWNER in ids
    assert OTHER not in ids


@pytest.mark.parametrize("table", ["outfit_garments", "wears"])
def test_rows_linked_through_outfits_stay_with_their_owner(snapshot, table):
    assert values(snapshot, table, "outfit_id") == {OWNER}


def test_disowned_garments_are_kept(snapshot):
    rows = snapshot.execute("SELECT disowned_on FROM garments WHERE id = ?", (DISOWNED_GARMENT,)).fetchall()
    assert rows == [("2026-11-01",)]


@pytest.mark.parametrize("table", ["garments", "wears"])
def test_notes_are_left_out(snapshot, table):
    with pytest.raises(sqlite3.OperationalError, match="no such column"):
        snapshot.execute(f"SELECT notes FROM {table}")


@pytest.mark.parametrize("table", INSIGHTS_SCHEMA)
def test_user_id_is_left_out(snapshot, table):
    with pytest.raises(sqlite3.OperationalError, match="no such column"):
        snapshot.execute(f"SELECT user_id FROM {table}")


def test_users_table_is_left_out(snapshot):
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        snapshot.execute("SELECT * FROM users")


def test_unknown_user_gets_empty_tables(db_path):
    with closing(build_snapshot(db_path, 999)) as conn:
        for table in INSIGHTS_SCHEMA:
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)


def test_snapshot_leaves_the_real_database_unchanged(db_path):
    before = db_path.read_bytes()
    with closing(build_snapshot(db_path, OWNER)):
        pass
    assert db_path.read_bytes() == before

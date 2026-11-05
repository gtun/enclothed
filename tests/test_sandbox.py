import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from enclothed import config, db
from enclothed.sandbox import INSIGHTS_SCHEMA, build_snapshot, insights_authorizer

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


# --- Guards -----------------------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "SELECT * FROM garments",
    "SELECT category, COUNT(*) FROM garments GROUP BY category",
    "SELECT g.id, o.aesthetic FROM garments g JOIN outfit_garments og ON og.garment_id = g.id JOIN outfits o ON o.id = og.outfit_id",
    "SELECT value FROM garments, json_each('[1, 2]')",
    "SELECT strftime('%Y', date_added) FROM garments",
    "WITH owned AS (SELECT * FROM garments WHERE disowned_on IS NULL) SELECT COUNT(*) FROM owned",
    "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 5) SELECT COUNT(*) FROM r",
])
def test_reads_still_work(snapshot, sql):
    snapshot.execute(sql).fetchall()


@pytest.mark.parametrize("sql", [
    "INSERT INTO sets (name) VALUES ('x')",
    "UPDATE garments SET brand = 'x'",
    "DELETE FROM garments",
    "DROP TABLE garments",
    "CREATE TABLE x (a)",
    "CREATE TEMP TABLE x (a)",
    "ALTER TABLE garments ADD COLUMN x TEXT",
    "PRAGMA query_only = OFF",
    "PRAGMA table_info(garments)",
    "ATTACH 'other.db' AS other",
    "VACUUM INTO 'copy.db'",
    "BEGIN",
])
def test_anything_but_a_read_is_refused(snapshot, sql):
    with pytest.raises(sqlite3.DatabaseError):
        snapshot.execute(sql)


def test_refused_writes_change_nothing(snapshot):
    before = snapshot.execute("SELECT COUNT(*) FROM garments").fetchone()
    with pytest.raises(sqlite3.DatabaseError):
        snapshot.execute("DELETE FROM garments")
    assert snapshot.execute("SELECT COUNT(*) FROM garments").fetchone() == before


def test_query_only_blocks_writes_without_the_authorizer(snapshot):
    """The second layer: if the authorizer were missing, writes would still fail."""
    snapshot.set_authorizer(None)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        snapshot.execute("DELETE FROM garments")


def test_authorizer_blocks_writes_without_query_only(snapshot):
    """The other layer: this fails unless the authorizer itself refuses the write."""
    snapshot.set_authorizer(None)
    snapshot.execute("PRAGMA query_only = OFF")
    snapshot.set_authorizer(insights_authorizer)
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        snapshot.execute("DELETE FROM garments")


@pytest.mark.parametrize("action", [
    sqlite3.SQLITE_INSERT,
    sqlite3.SQLITE_UPDATE,
    sqlite3.SQLITE_DELETE,
    sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_CREATE_TABLE,
    sqlite3.SQLITE_ALTER_TABLE,
    sqlite3.SQLITE_PRAGMA,
    sqlite3.SQLITE_ATTACH,
    sqlite3.SQLITE_TRANSACTION,
])
def test_authorizer_denies_each_write_action(action):
    """Python opens a transaction before a write, so denying that alone would hide a gap here."""
    assert insights_authorizer(action, None, None, None, None) == sqlite3.SQLITE_DENY


def test_a_second_statement_is_refused(snapshot):
    with pytest.raises(sqlite3.ProgrammingError):
        snapshot.execute("SELECT 1; DELETE FROM garments")


@pytest.mark.parametrize("sql", [
    "SELECT randomblob(900000000)",
    "SELECT zeroblob(900000000)",
    "SELECT hex(randomblob(400000000))",
])
def test_huge_values_are_refused(snapshot, sql):
    with pytest.raises(sqlite3.DataError, match="too big"):
        snapshot.execute(sql).fetchall()


def test_values_up_to_the_limit_work(snapshot):
    assert snapshot.execute(f"SELECT length(zeroblob({config.INSIGHTS_VALUE_SIZE_LIMIT}))").fetchone() == (config.INSIGHTS_VALUE_SIZE_LIMIT,)

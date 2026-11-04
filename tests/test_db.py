import sqlite3
from datetime import date
from contextlib import closing

import pytest
from pydantic import ValidationError

from enclothed.db import select_preferences, save_preferences, init_db, insert_garment, insert_outfits, select_garment, DB_DEFAULT_FIELDS, select_all_sets, insert_set, update_garment, set_outfit_liked, select_owned_garments, select_all_garments, select_outfit, select_all_outfits
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

def test_update_changes_fields(db_path):
    garment_id = insert_garment(db_path, TEST_GARMENT)
    original = select_garment(db_path, garment_id)

    edited = original.model_copy(update={"primary_color": "navy", "style_tags": ["edited"], "notes": "faded"})
    update_garment(db_path, edited)
    updated = select_garment(db_path, garment_id)

    assert updated.primary_color == "navy"
    assert updated.style_tags == ["edited"]
    assert updated.notes == "faded"
    assert updated.id == original.id
    assert updated.date_added == original.date_added

def test_update_only_touches_its_own_row(db_path):
    target_id = insert_garment(db_path, TEST_GARMENT)
    other_id = insert_garment(db_path, TEST_GARMENT)

    edited = select_garment(db_path, target_id).model_copy(update={"primary_color": "navy"})
    update_garment(db_path, edited)

    assert select_garment(db_path, other_id).primary_color == TEST_GARMENT.primary_color


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


def _insert_two_garments(db_path):
    return [insert_garment(db_path, TEST_GARMENT) for _ in range(2)]


def test_named_set(db_path):
    garment_ids = _insert_two_garments(db_path)
    set_id = insert_set(db_path, garment_ids, "navy suit")
    assert select_all_sets(db_path) == {set_id: "navy suit"}


def test_unnamed_set(db_path):
    garment_ids = _insert_two_garments(db_path)
    set_id = insert_set(db_path, garment_ids, None)
    assert select_all_sets(db_path) == {set_id: None}


def test_empty_sets_table(db_path):
    assert select_all_sets(db_path) == {}

def test_insert_set_unknown_garment_raises_and_rolls_back(db_path):
    garment_id = insert_garment(db_path, TEST_GARMENT)
    with pytest.raises(ValueError, match="updated 1"):
        insert_set(db_path, [garment_id, 999], "ghost suit")
    # The rollback undid both the sets row and the garment's update.
    assert select_all_sets(db_path) == {}
    assert select_garment(db_path, garment_id).set_id is None


def test_insert_set_garment_already_in_set_raises_and_rolls_back(db_path):
    jacket, trousers, shoes = [insert_garment(db_path, TEST_GARMENT) for _ in range(3)]
    first_set = insert_set(db_path, [jacket, trousers], "navy suit")
    with pytest.raises(ValueError, match="updated 1"):
        insert_set(db_path, [trousers, shoes], None)
    # Only the first set exists; trousers kept their set, shoes stayed free.
    assert select_all_sets(db_path) == {first_set: "navy suit"}
    assert select_garment(db_path, trousers).set_id == first_set
    assert select_garment(db_path, shoes).set_id is None


# --- set_outfit_liked ---------------------------------------------------------------

def liked_value(db_path, outfit_id):
    return rows(db_path, f"SELECT liked FROM outfits WHERE id = {outfit_id}")[0]["liked"]


@pytest.mark.parametrize("liked, stored", [(True, 1), (False, 0), (None, None)])
def test_set_outfit_liked_stores_value(db_path, garment_ids, liked, stored):
    [outfit_id] = insert_outfits(db_path, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    assert set_outfit_liked(db_path, outfit_id, liked) is True
    assert liked_value(db_path, outfit_id) == stored


def test_set_outfit_liked_can_clear_back_to_unrated(db_path, garment_ids):
    [outfit_id] = insert_outfits(db_path, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    set_outfit_liked(db_path, outfit_id, True)
    set_outfit_liked(db_path, outfit_id, None)
    assert liked_value(db_path, outfit_id) is None


def test_set_outfit_liked_missing_id_returns_false(db_path):
    assert set_outfit_liked(db_path, 999, True) is False


def test_set_outfit_liked_only_touches_its_own_row(db_path, garment_ids):
    target_id, other_id = insert_outfits(db_path, [make_outfit(garment_ids), make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    set_outfit_liked(db_path, target_id, True)
    assert liked_value(db_path, other_id) is None


@pytest.mark.parametrize("bad", [-1, 2, "yes"])
def test_set_outfit_liked_rejects_bad_values(db_path, garment_ids, bad):
    [outfit_id] = insert_outfits(db_path, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    with pytest.raises(ValueError):
        set_outfit_liked(db_path, outfit_id, bad)
    assert liked_value(db_path, outfit_id) is None


# --- preferences ---------------------------------------------------------------------

def test_preferences_round_trip(db_path):
    assert select_preferences(db_path, 1) is None
    save_preferences(db_path, 1, "loose fits", "2026-11-01T00:00:00+00:00")
    save_preferences(db_path, 1, "loose fits; no shorts", "2026-11-02T00:00:00+00:00")
    assert select_preferences(db_path, 1) == ("loose fits; no shorts", "2026-11-02T00:00:00+00:00")
    save_preferences(db_path, 1, None, "2026-11-03T00:00:00+00:00")
    assert select_preferences(db_path, 1) is None


def test_preferences_migration_adds_table_to_an_existing_db(tmp_path):
    from enclothed.config import SCHEMA_PATH, MIGRATIONS_DIR
    path = tmp_path / "old.db"
    old_schema = tmp_path / "old_schema.sql"
    old_schema.write_text(SCHEMA_PATH.read_text().split("CREATE TABLE IF NOT EXISTS preferences")[0])
    old_migrations = tmp_path / "old_migrations"; old_migrations.mkdir()
    upto_003 = tmp_path / "upto_003"; upto_003.mkdir()
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for m in migrations[:2]:
        (old_migrations / m.name).write_text(m.read_text())
    for m in migrations[:3]:
        (upto_003 / m.name).write_text(m.read_text())
    init_db(path, old_schema, old_migrations)  # a database as it was before preferences existed

    init_db(path, old_schema, upto_003)  # old_schema has no preferences table, so only migration 003 can create it
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'preferences'").fetchone()


# --- disowning garments -----------------------------------------------------------------
def disown(db_path, garment_id, day="2026-11-03"):
    garment = select_garment(db_path, garment_id)
    update_garment(db_path, garment.model_copy(update={"disowned_on": date.fromisoformat(day)}))


def test_disowned_on_migration_leaves_existing_garments_owned(tmp_path):
    path = tmp_path / "old.db"
    old_schema = tmp_path / "old_schema.sql"
    old_schema.write_text(SCHEMA_PATH.read_text().replace(",\n    disowned_on TEXT", "") + PREFERENCES_TABLE)
    upto_003 = tmp_path / "upto_003"; upto_003.mkdir()
    for m in sorted(MIGRATIONS_DIR.glob("*.sql"))[:3]:
        (upto_003 / m.name).write_text(m.read_text())
    init_db(path, old_schema, upto_003)
    with closing(sqlite3.connect(path)) as conn:
        assert "disowned_on" not in {col[1] for col in conn.execute("PRAGMA table_info(garments)")}
        conn.execute("INSERT INTO garments (category, subcategory, primary_color, styling_notes) VALUES ('top', 't-shirt', 'black', '')")
        conn.commit()

    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)

    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM garments WHERE disowned_on IS NULL").fetchone()[0] == 1


def test_disowned_on_round_trips(db_path):
    garment_id = insert_garment(db_path, TEST_GARMENT)
    disown(db_path, garment_id)
    assert select_garment(db_path, garment_id).disowned_on == date(2026, 11, 3)


def test_select_owned_garments_leaves_out_disowned(db_path):
    kept = insert_garment(db_path, TEST_GARMENT)
    gone = insert_garment(db_path, TEST_GARMENT)
    disown(db_path, gone)
    assert [g.id for g in select_owned_garments(db_path)] == [kept]


def test_select_all_garments_keeps_disowned(db_path):
    kept = insert_garment(db_path, TEST_GARMENT)
    gone = insert_garment(db_path, TEST_GARMENT)
    disown(db_path, gone)
    assert [g.id for g in select_all_garments(db_path)] == [kept, gone]


# --- wear_count ---------------------------------------------------------------------------
def outfit_with_garments(db_path, count):
    garment_ids = [insert_garment(db_path, TEST_GARMENT) for _ in range(count)]
    outfit = Outfit(aesthetic="a", explanation="b", garments=[{"garment_id": i} for i in garment_ids])
    [outfit_id] = insert_outfits(db_path, [outfit], None, "dinner", "2026-11-01T00:00:00+00:00")
    return outfit_id


def add_wears(db_path, outfit_id, count):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            for _ in range(count):
                conn.execute("INSERT INTO wears (outfit_id, date) VALUES (?, '2026-11-01')", (outfit_id,))


def test_wear_count_is_zero_without_wears(db_path):
    assert select_outfit(db_path, outfit_with_garments(db_path, 2))["wear_count"] == 0


def test_wear_count_is_not_multiplied_by_garments(db_path):
    outfit_id = outfit_with_garments(db_path, 4)
    add_wears(db_path, outfit_id, 2)
    assert select_outfit(db_path, outfit_id)["wear_count"] == 2
    assert select_all_outfits(db_path)[0]["wear_count"] == 2


# --- users ---------------------------------------------------------------------------
PREFERENCES_TABLE = """
CREATE TABLE preferences (
    id INTEGER PRIMARY KEY NOT NULL CHECK (id = 1),
    text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def make_v4_db(tmp_path):
    """A database as it was before users existed, with its preferences table."""
    path = tmp_path / "old.db"
    old_schema = tmp_path / "old_schema.sql"
    old_schema.write_text(SCHEMA_PATH.read_text().split("CREATE TABLE IF NOT EXISTS users")[0] + PREFERENCES_TABLE)
    upto_004 = tmp_path / "upto_004"; upto_004.mkdir()
    for m in sorted(MIGRATIONS_DIR.glob("*.sql"))[:4]:
        (upto_004 / m.name).write_text(m.read_text())
    init_db(path, old_schema, upto_004)
    return path


def test_users_migration_carries_saved_preferences_over(tmp_path):
    path = make_v4_db(tmp_path)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute("INSERT INTO preferences VALUES (1, 'loose fits', '2026-11-01T00:00:00+00:00')")

    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)

    assert select_preferences(path, 1) == ("loose fits", "2026-11-01T00:00:00+00:00")
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'preferences'").fetchone() is None
        assert conn.execute("SELECT id, username, is_admin FROM users").fetchall() == [(1, "owner", 1)]


def test_users_migration_with_no_saved_preferences(tmp_path):
    path = make_v4_db(tmp_path)
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    assert select_preferences(path, 1) is None


def test_fresh_db_and_restart_keep_one_owner(db_path):
    init_db(db_path, SCHEMA_PATH, MIGRATIONS_DIR)   # init_db runs on every start
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT id, username, is_admin FROM users").fetchall() == [(1, "owner", 1)]


def test_preferences_belong_to_one_user(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("INSERT INTO users (id, username) VALUES (2, 'other')")
    save_preferences(db_path, 1, "loose fits", "2026-11-01T00:00:00+00:00")
    assert select_preferences(db_path, 2) is None

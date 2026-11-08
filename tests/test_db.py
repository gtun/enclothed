import sqlite3
from datetime import date
from contextlib import closing

import pytest
from pydantic import ValidationError

from enclothed.db import insert_user, select_user, update_user, select_preferences, save_preferences, init_db, insert_garment, insert_outfits, select_garment, DB_DEFAULT_FIELDS, select_all_sets, insert_set, update_garment, set_outfit_liked, select_owned_garments, select_all_garments, select_outfit, select_all_outfits
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
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    new_garment = select_garment(db_path, 1, garment_id)

    assert new_garment is not None, f"Garment {garment_id} was not found"
    assert new_garment.id == garment_id
    assert TEST_GARMENT.model_dump(exclude=DB_DEFAULT_FIELDS) == new_garment.model_dump(exclude=DB_DEFAULT_FIELDS)

def test_select_missing_id_returns_none(db_path):
    new_garment = select_garment(db_path, 1, -5)

    assert new_garment is None

def test_select_rejects_out_of_range_formality(db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("UPDATE garments SET formality=8 WHERE id = :id;", {"id":garment_id})

    with pytest.raises(ValidationError):
        select_garment(db_path, 1, garment_id)

def test_select_rejects_null_accent_colors(db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("UPDATE garments SET accent_colors=NULL WHERE id = :id;", {"id":garment_id})

    with pytest.raises(ValidationError):
        select_garment(db_path, 1, garment_id)

def test_update_changes_fields(db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    original = select_garment(db_path, 1, garment_id)

    edited = original.model_copy(update={"primary_color": "navy", "style_tags": ["edited"], "notes": "faded"})
    update_garment(db_path, 1, edited)
    updated = select_garment(db_path, 1, garment_id)

    assert updated.primary_color == "navy"
    assert updated.style_tags == ["edited"]
    assert updated.notes == "faded"
    assert updated.id == original.id
    assert updated.date_added == original.date_added

def test_update_only_touches_its_own_row(db_path):
    target_id = insert_garment(db_path, 1, TEST_GARMENT)
    other_id = insert_garment(db_path, 1, TEST_GARMENT)

    edited = select_garment(db_path, 1, target_id).model_copy(update={"primary_color": "navy"})
    update_garment(db_path, 1, edited)

    assert select_garment(db_path, 1, other_id).primary_color == TEST_GARMENT.primary_color


# --- insert_outfits -----------------------------------------------------------------
# outfit_garments has foreign keys to garments, so each test inserts real garments first.

TIMESTAMP = "2026-10-26T22:00:00+00:00"


@pytest.fixture
def garment_ids(db_path):
    """Three real garment rows; returns their ids."""
    return [insert_garment(db_path, 1, TEST_GARMENT) for _ in range(3)]


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
    new_ids = insert_outfits(db_path, 1, outfits, None, "dinner", TIMESTAMP)
    assert len(new_ids) == 2
    assert len(set(new_ids)) == 2
    assert [r["id"] for r in rows(db_path, "SELECT id FROM outfits ORDER BY id")] == new_ids


def test_insert_outfits_writes_outfit_rows(db_path, garment_ids):
    outfits = [make_outfit(garment_ids, aesthetic="A"), make_outfit(garment_ids, aesthetic="B", missing="a belt")]
    insert_outfits(db_path, 1, outfits, None, "dinner downtown", TIMESTAMP)
    saved = rows(db_path, "SELECT timestamp, prompt_message, aesthetic, explanation, missing, liked FROM outfits ORDER BY id")
    assert saved == [
        {"timestamp": TIMESTAMP, "prompt_message": "dinner downtown", "aesthetic": "A",
         "explanation": "why it works", "missing": None, "liked": None},
        {"timestamp": TIMESTAMP, "prompt_message": "dinner downtown", "aesthetic": "B",
         "explanation": "why it works", "missing": "a belt", "liked": None},
    ]


def test_insert_outfits_writes_garment_rows_with_advice(db_path, garment_ids):
    [outfit_id] = insert_outfits(db_path, 1, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    saved = rows(db_path, "SELECT outfit_id, garment_id, styling_advice FROM outfit_garments ORDER BY garment_id")
    assert saved == [
        {"outfit_id": outfit_id, "garment_id": i, "styling_advice": f"advice {i}"} for i in garment_ids
    ]


def test_insert_outfits_marks_anchors(db_path, garment_ids):
    anchor = garment_ids[0]
    insert_outfits(db_path, 1, [make_outfit(garment_ids)], [anchor], "dinner", TIMESTAMP)
    saved = rows(db_path, "SELECT garment_id, is_anchor FROM outfit_garments ORDER BY garment_id")
    assert saved == [{"garment_id": i, "is_anchor": 1 if i == anchor else 0} for i in garment_ids]


def test_insert_outfits_without_anchors_marks_none(db_path, garment_ids):
    insert_outfits(db_path, 1, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    assert {r["is_anchor"] for r in rows(db_path, "SELECT is_anchor FROM outfit_garments")} == {0}


def test_insert_outfits_empty_list_writes_nothing(db_path):
    assert insert_outfits(db_path, 1, [], None, "dinner", TIMESTAMP) == []
    assert rows(db_path, "SELECT * FROM outfits") == []


def test_insert_outfits_is_all_or_nothing(db_path, garment_ids):
    # The second outfit points at a garment that doesn't exist. The foreign key rejects it,
    # and the transaction must roll back the first outfit too: no half-saved replies.
    outfits = [make_outfit(garment_ids), make_outfit([garment_ids[0], 999])]
    with pytest.raises(sqlite3.IntegrityError):
        insert_outfits(db_path, 1, outfits, None, "dinner", TIMESTAMP)
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


# Migration 006 alters these, so an old database has to have them already.
OLD_SETS_AND_OUTFITS = """
CREATE TABLE sets (id INTEGER PRIMARY KEY NOT NULL, name TEXT);
CREATE TABLE outfits (
    id INTEGER PRIMARY KEY NOT NULL,
    timestamp TEXT NOT NULL,
    prompt_message TEXT NOT NULL,
    aesthetic TEXT NOT NULL,
    explanation TEXT NOT NULL,
    missing TEXT,
    liked INTEGER DEFAULT NULL,
    CHECK (liked in (0, 1))
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
            conn.executescript(OLD_SETS_AND_OUTFITS)
            conn.execute("INSERT INTO garments (category, wear_count) VALUES ('top', 3), ('shoes', 0)")


NEW_ATTRIBUTES = {"fabric_type", "shape", "hem", "fabric_weight", "sleeve", "statement", "mended_on"}
LATER_COLUMNS = NEW_ATTRIBUTES | {"risk_tier"}   # every column added by a migration after 008


def schema_before_user_id():
    """schema.sql as it was before migration 006 added user_id."""
    text = SCHEMA_PATH.read_text()
    text = text.replace(",\n    language TEXT NOT NULL DEFAULT 'en-US',\n    is_demo INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),\n    demo_reset_at TEXT", "")   # added later, by migrations 007 and 008
    text = text.replace(",\n    user_id INTEGER REFERENCES users(id)", "")
    text = text.replace("    user_id INTEGER REFERENCES users(id),\n", "")
    return "".join(line for line in text.splitlines(keepends=True) if line.strip().split(" ")[0] not in LATER_COLUMNS)


LATEST = max(int(p.name.split("_")[0]) for p in MIGRATIONS_DIR.glob("*.sql"))


def test_attributes_migration_keeps_garments_and_leaves_the_new_fields_blank(tmp_path):
    path = tmp_path / "old.db"
    old_schema = tmp_path / "old_schema.sql"
    old_schema.write_text("".join(
        line for line in SCHEMA_PATH.read_text().splitlines(keepends=True)
        if line.strip().split(" ")[0] not in LATER_COLUMNS
    ))
    upto_008 = tmp_path / "upto_008"; upto_008.mkdir()
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql"))[:8]:
        (upto_008 / migration.name).write_text(migration.read_text())
    init_db(path, old_schema, upto_008)
    with closing(sqlite3.connect(path)) as conn:
        assert not NEW_ATTRIBUTES & {col[1] for col in conn.execute("PRAGMA table_info(garments)")}
        conn.execute("INSERT INTO garments (category, subcategory, primary_color, secondary_colors, accent_colors, materials, style_tags, styling_notes, user_id) "
                     "VALUES ('top', 't-shirt', 'black', '[]', '[]', '[]', '[]', 'x', 1)")
        conn.commit()

    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)

    [garment] = select_all_garments(path, 1)
    assert garment.subcategory == "t-shirt"
    assert all(getattr(garment, field) is None for field in NEW_ATTRIBUTES)


def test_new_attributes_survive_a_save_and_load(db_path):
    garment = TEST_GARMENT.model_copy(update=dict(fabric_type="corduroy", shape="tapered", hem="ankle", fabric_weight="heavy", sleeve=None, statement="feature"))
    saved = select_garment(db_path, 1, insert_garment(db_path, 1, garment))
    assert (saved.fabric_type, saved.shape, saved.hem, saved.fabric_weight, saved.statement) == ("corduroy", "tapered", "ankle", "heavy", "feature")


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
    return [insert_garment(db_path, 1, TEST_GARMENT) for _ in range(2)]


def test_named_set(db_path):
    garment_ids = _insert_two_garments(db_path)
    set_id = insert_set(db_path, 1, garment_ids, "navy suit")
    assert select_all_sets(db_path, 1) == {set_id: "navy suit"}


def test_unnamed_set(db_path):
    garment_ids = _insert_two_garments(db_path)
    set_id = insert_set(db_path, 1, garment_ids, None)
    assert select_all_sets(db_path, 1) == {set_id: None}


def test_empty_sets_table(db_path):
    assert select_all_sets(db_path, 1) == {}

def test_insert_set_unknown_garment_raises_and_rolls_back(db_path):
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    with pytest.raises(ValueError, match="updated 1"):
        insert_set(db_path, 1, [garment_id, 999], "ghost suit")
    # The rollback undid both the sets row and the garment's update.
    assert select_all_sets(db_path, 1) == {}
    assert select_garment(db_path, 1, garment_id).set_id is None


def test_insert_set_garment_already_in_set_raises_and_rolls_back(db_path):
    jacket, trousers, shoes = [insert_garment(db_path, 1, TEST_GARMENT) for _ in range(3)]
    first_set = insert_set(db_path, 1, [jacket, trousers], "navy suit")
    with pytest.raises(ValueError, match="updated 1"):
        insert_set(db_path, 1, [trousers, shoes], None)
    # Only the first set exists; trousers kept their set, shoes stayed free.
    assert select_all_sets(db_path, 1) == {first_set: "navy suit"}
    assert select_garment(db_path, 1, trousers).set_id == first_set
    assert select_garment(db_path, 1, shoes).set_id is None


# --- set_outfit_liked ---------------------------------------------------------------

def liked_value(db_path, outfit_id):
    return rows(db_path, f"SELECT liked FROM outfits WHERE id = {outfit_id}")[0]["liked"]


@pytest.mark.parametrize("liked, stored", [(True, 1), (False, 0), (None, None)])
def test_set_outfit_liked_stores_value(db_path, garment_ids, liked, stored):
    [outfit_id] = insert_outfits(db_path, 1, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    assert set_outfit_liked(db_path, 1, outfit_id, liked) is True
    assert liked_value(db_path, outfit_id) == stored


def test_set_outfit_liked_can_clear_back_to_unrated(db_path, garment_ids):
    [outfit_id] = insert_outfits(db_path, 1, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    set_outfit_liked(db_path, 1, outfit_id, True)
    set_outfit_liked(db_path, 1, outfit_id, None)
    assert liked_value(db_path, outfit_id) is None


def test_set_outfit_liked_missing_id_returns_false(db_path):
    assert set_outfit_liked(db_path, 1, 999, True) is False


def test_set_outfit_liked_only_touches_its_own_row(db_path, garment_ids):
    target_id, other_id = insert_outfits(db_path, 1, [make_outfit(garment_ids), make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    set_outfit_liked(db_path, 1, target_id, True)
    assert liked_value(db_path, other_id) is None


@pytest.mark.parametrize("bad", [-1, 2, "yes"])
def test_set_outfit_liked_rejects_bad_values(db_path, garment_ids, bad):
    [outfit_id] = insert_outfits(db_path, 1, [make_outfit(garment_ids)], None, "dinner", TIMESTAMP)
    with pytest.raises(ValueError):
        set_outfit_liked(db_path, 1, outfit_id, bad)
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
    garment = select_garment(db_path, 1, garment_id)
    update_garment(db_path, 1, garment.model_copy(update={"disowned_on": date.fromisoformat(day)}))


def test_disowned_on_migration_leaves_existing_garments_owned(tmp_path):
    path = tmp_path / "old.db"
    old_schema = tmp_path / "old_schema.sql"
    old_schema.write_text(schema_before_user_id().replace(",\n    disowned_on TEXT", "") + PREFERENCES_TABLE)
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
    garment_id = insert_garment(db_path, 1, TEST_GARMENT)
    disown(db_path, garment_id)
    assert select_garment(db_path, 1, garment_id).disowned_on == date(2026, 11, 3)


def test_select_owned_garments_leaves_out_disowned(db_path):
    kept = insert_garment(db_path, 1, TEST_GARMENT)
    gone = insert_garment(db_path, 1, TEST_GARMENT)
    disown(db_path, gone)
    assert [g.id for g in select_owned_garments(db_path, 1)] == [kept]


def test_select_all_garments_keeps_disowned(db_path):
    kept = insert_garment(db_path, 1, TEST_GARMENT)
    gone = insert_garment(db_path, 1, TEST_GARMENT)
    disown(db_path, gone)
    assert [g.id for g in select_all_garments(db_path, 1)] == [kept, gone]


# --- wear_count ---------------------------------------------------------------------------
def outfit_with_garments(db_path, count):
    garment_ids = [insert_garment(db_path, 1, TEST_GARMENT) for _ in range(count)]
    outfit = Outfit(aesthetic="a", explanation="b", garments=[{"garment_id": i} for i in garment_ids])
    [outfit_id] = insert_outfits(db_path, 1, [outfit], None, "dinner", "2026-11-01T00:00:00+00:00")
    return outfit_id


def add_wears(db_path, outfit_id, count):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            for _ in range(count):
                conn.execute("INSERT INTO wears (outfit_id, date) VALUES (?, '2026-11-01')", (outfit_id,))


def test_wear_count_is_zero_without_wears(db_path):
    assert select_outfit(db_path, 1, outfit_with_garments(db_path, 2))["wear_count"] == 0


def test_wear_count_is_not_multiplied_by_garments(db_path):
    outfit_id = outfit_with_garments(db_path, 4)
    add_wears(db_path, outfit_id, 2)
    assert select_outfit(db_path, 1, outfit_id)["wear_count"] == 2
    assert select_all_outfits(db_path, 1)[0]["wear_count"] == 2


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
    old_schema.write_text(schema_before_user_id().split("CREATE TABLE IF NOT EXISTS users")[0] + PREFERENCES_TABLE)
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


def make_v5_db(tmp_path):
    """A database as it was before user_id, with one row in each table it was added to."""
    path = tmp_path / "old.db"
    old_schema = tmp_path / "old_schema.sql"
    old_schema.write_text(schema_before_user_id())
    upto_005 = tmp_path / "upto_005"; upto_005.mkdir()
    for m in sorted(MIGRATIONS_DIR.glob("*.sql"))[:5]:
        (upto_005 / m.name).write_text(m.read_text())
    init_db(path, old_schema, upto_005)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute("INSERT INTO sets (name) VALUES ('suit')")
            conn.execute("INSERT INTO garments (category, subcategory, primary_color, styling_notes) VALUES ('top', 't-shirt', 'black', '')")
            conn.execute("INSERT INTO outfits (timestamp, prompt_message, aesthetic, explanation) VALUES ('t', 'p', 'a', 'e')")
    return path


@pytest.mark.parametrize("table", ["garments", "sets", "outfits"])
def test_user_id_migration_gives_existing_rows_to_the_owner(tmp_path, table):
    path = make_v5_db(tmp_path)
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute(f"SELECT user_id FROM {table}").fetchall() == [(1,)]


def test_new_rows_record_their_owner(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("INSERT INTO users (id, username) VALUES (2, 'other')")
    garment_id = insert_garment(db_path, 2, TEST_GARMENT)
    set_id = insert_set(db_path, 2, [garment_id], None)
    [outfit_id] = insert_outfits(db_path, 2, [make_outfit([garment_id])], None, "dinner", TIMESTAMP)
    assert select_garment(db_path, 2, garment_id).user_id == 2
    assert rows(db_path, f"SELECT user_id FROM sets WHERE id = {set_id}") == [{"user_id": 2}]
    assert rows(db_path, f"SELECT user_id FROM outfits WHERE id = {outfit_id}") == [{"user_id": 2}]


def test_editing_a_garment_keeps_its_owner(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("INSERT INTO users (id, username) VALUES (2, 'other')")
    garment_id = insert_garment(db_path, 2, TEST_GARMENT)
    edited = select_garment(db_path, 2, garment_id).model_copy(update={"notes": "new", "user_id": 1})
    update_garment(db_path, 2, edited)
    assert select_garment(db_path, 2, garment_id).user_id == 2


def test_updating_someone_elses_garment_changes_nothing(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("INSERT INTO users (id, username) VALUES (2, 'other')")
    garment_id = insert_garment(db_path, 2, TEST_GARMENT)
    edited = select_garment(db_path, 2, garment_id).model_copy(update={"notes": "changed by user 1"})
    update_garment(db_path, 1, edited)
    assert select_garment(db_path, 2, garment_id).notes != "changed by user 1"


def test_a_set_cannot_take_another_users_garment(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("INSERT INTO users (id, username) VALUES (2, 'other')")
    garment_id = insert_garment(db_path, 2, TEST_GARMENT)
    with pytest.raises(ValueError):
        insert_set(db_path, 1, [garment_id], "stolen")


def test_preferences_belong_to_one_user(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("INSERT INTO users (id, username) VALUES (2, 'other')")
    save_preferences(db_path, 1, "loose fits", "2026-11-01T00:00:00+00:00")
    assert select_preferences(db_path, 2) is None


def test_insert_user_stores_email_lowercase(db_path):
    user_id = insert_user(db_path, "kim", "Kim@Example.COM")
    assert select_user(db_path, user_id).email == "kim@example.com"


def test_insert_user_rejects_the_same_email_in_another_case(db_path):
    insert_user(db_path, "kim", "kim@example.com")
    with pytest.raises(sqlite3.IntegrityError):
        insert_user(db_path, "kim2", "KIM@example.com")


def test_update_user_changes_name_and_email(db_path):
    update_user(db_path, 1, "gtun", "Owner@Example.com")
    user = select_user(db_path, 1)
    assert (user.username, user.email, user.is_admin) == ("gtun", "owner@example.com", True)


def test_language_migration_defaults_everyone_to_english(tmp_path):
    path = tmp_path / "test.db"
    old_schema = tmp_path / "old_schema.sql"
    old_schema.write_text(schema_before_user_id())
    upto_006 = tmp_path / "upto_006"; upto_006.mkdir()
    for m in sorted(MIGRATIONS_DIR.glob("*.sql"))[:6]:
        (upto_006 / m.name).write_text(m.read_text())
    init_db(path, old_schema, upto_006)

    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    assert select_user(path, 1).language == "en-US"


def test_older_db_without_a_users_table_still_reaches_the_latest_version(tmp_path):
    """schema.sql is for new databases only. Run on this one, it would create users with the
    language column already there, and migration 007 would fail on adding it."""
    path = tmp_path / "test.db"
    make_old_db(path)
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    assert user_version(path) == LATEST
    assert select_user(path, 1).language == "en-US"

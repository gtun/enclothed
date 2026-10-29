import re
import sqlite3
import sys
from contextlib import closing

import pytest

from enclothed import config, db
from enclothed.intake import TEST_GARMENT
from enclothed.main import main


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """A temp DB with 3 garments (ids 1, 2, 3), and config pointed at tmp_path
    so main() never touches the real data/ folder."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(config, "INTAKE_DIR", tmp_path / "intake")
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    for _ in range(3):
        db.insert_garment(path, TEST_GARMENT.model_copy())
    return path


def run_set(monkeypatch, *cli_args):
    """Run `enclothed set <cli_args>` and return main()'s exit code."""
    monkeypatch.setattr(sys, "argv", ["enclothed", "set", *cli_args])
    return main()


def run_set_expecting_error(monkeypatch, capsys, *cli_args):
    """Run `enclothed set <cli_args>`, assert it exits through set_parser.error
    (SystemExit with code 2), and return what it wrote to stderr."""
    with pytest.raises(SystemExit) as exc_info:
        run_set(monkeypatch, *cli_args)
    assert exc_info.value.code == 2
    return capsys.readouterr().err


def ids_in_message(stderr):
    """Every integer in the error message, as a set (output order doesn't matter).
    Only looks after 'error:', so the usage line's text can't add numbers."""
    message = stderr.split("error:", 1)[1]
    return {int(n) for n in re.findall(r"-?\d+", message)}


def all_sets(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("SELECT id, name FROM sets ORDER BY id").fetchall()


def set_ids_by_garment(path):
    with closing(sqlite3.connect(path)) as conn:
        return dict(conn.execute("SELECT id, set_id FROM garments ORDER BY id").fetchall())


NOTHING_SET = {1: None, 2: None, 3: None}


# --- 1. unknown ids -----------------------------------------------------------

def test_unknown_ids_are_reported_and_nothing_is_written(db_path, monkeypatch, capsys):
    stderr = run_set_expecting_error(monkeypatch, capsys, "-g", "1", "0", "-5", "999999")

    assert ids_in_message(stderr) == {0, -5, 999999}  # only the bad ids, not 1
    assert all_sets(db_path) == []
    assert set_ids_by_garment(db_path) == NOTHING_SET


# --- 2. garments already in a set ---------------------------------------------

def test_garments_already_in_a_set_are_reported_and_nothing_is_written(db_path, monkeypatch, capsys):
    existing_set = db.insert_set(db_path, [1, 2], "existing")

    stderr = run_set_expecting_error(monkeypatch, capsys, "-g", "1", "2", "3")

    assert ids_in_message(stderr) == {1, 2}  # only the taken ids, not 3
    assert all_sets(db_path) == [(existing_set, "existing")]
    assert set_ids_by_garment(db_path) == {1: existing_set, 2: existing_set, 3: None}


# --- 3. fewer than two unique garments ----------------------------------------

def test_one_garment_is_rejected_and_nothing_is_written(db_path, monkeypatch, capsys):
    run_set_expecting_error(monkeypatch, capsys, "-g", "1")

    assert all_sets(db_path) == []
    assert set_ids_by_garment(db_path) == NOTHING_SET


def test_one_garment_repeated_is_rejected_and_nothing_is_written(db_path, monkeypatch, capsys):
    run_set_expecting_error(monkeypatch, capsys, "-g", "1", "1")

    assert all_sets(db_path) == []
    assert set_ids_by_garment(db_path) == NOTHING_SET


# --- 4. valid input -----------------------------------------------------------

def test_valid_set_is_inserted_and_garments_updated(db_path, monkeypatch, caplog):
    exit_code = run_set(monkeypatch, "-n", "suit", "-g", "1", "2")

    assert exit_code == 0
    sets = all_sets(db_path)
    assert len(sets) == 1
    new_set_id, name = sets[0]
    assert name == "suit"
    assert set_ids_by_garment(db_path) == {1: new_set_id, 2: new_set_id, 3: None}
    assert "Creating set" in caplog.text


def test_valid_set_without_a_name_stores_null(db_path, monkeypatch):
    exit_code = run_set(monkeypatch, "-g", "2", "3")

    assert exit_code == 0
    sets = all_sets(db_path)
    assert len(sets) == 1
    new_set_id, name = sets[0]
    assert name is None
    assert set_ids_by_garment(db_path) == {1: None, 2: new_set_id, 3: new_set_id}


def test_duplicate_ids_collapse_into_one_set(db_path, monkeypatch):
    # Two unique garments given three times in total: allowed, duplicates ignored
    exit_code = run_set(monkeypatch, "-g", "1", "2", "2")

    assert exit_code == 0
    sets = all_sets(db_path)
    assert len(sets) == 1
    new_set_id, _ = sets[0]
    assert set_ids_by_garment(db_path) == {1: new_set_id, 2: new_set_id, 3: None}

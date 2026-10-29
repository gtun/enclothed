# tests/test_add_command.py
# Runs `enclothed add` through main(), like test_set.py, to check the up-front
# photo path check (#9). All runs use -t, so no client is built and no tokens
# are spent; staging, insert and filing still run for real in tmp_path.
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

from enclothed import config, db
from enclothed.main import main

PHOTO = str(Path(__file__).parent / "fixtures" / "20261017_120645.jpg")


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """An empty temp DB, and config pointed at tmp_path so main() never
    touches the real data/ folder."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(config, "INTAKE_DIR", tmp_path / "intake")
    monkeypatch.setattr(config, "TAGGING_LOG_PATH", tmp_path / "tagging_log.jsonl")
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    return path


def run_add(monkeypatch, *cli_args):
    """Run `enclothed add <cli_args>` and return main()'s exit code."""
    monkeypatch.setattr(sys, "argv", ["enclothed", "add", *cli_args])
    return main()


def run_add_expecting_error(monkeypatch, capsys, *cli_args):
    """Run `enclothed add <cli_args>`, assert it exits through add_parser.error
    (SystemExit with code 2), and return the error message (after 'error:')."""
    with pytest.raises(SystemExit) as exc_info:
        run_add(monkeypatch, *cli_args)
    assert exc_info.value.code == 2
    return capsys.readouterr().err.split("error:", 1)[1]


def garment_count(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM garments").fetchone()[0]


# --- bad paths are rejected before anything runs ------------------------------

def test_missing_path_is_reported_and_nothing_is_written(db_path, monkeypatch, capsys):
    message = run_add_expecting_error(monkeypatch, capsys, "-t", "nope.jpg")

    assert "'nope.jpg'" in message
    assert garment_count(db_path) == 0
    assert not config.TAGGING_LOG_PATH.exists()


def test_all_missing_paths_are_reported_together(db_path, monkeypatch, capsys):
    message = run_add_expecting_error(monkeypatch, capsys, "-t", "a.jpg", PHOTO, "b.jpg")

    assert "'a.jpg'" in message
    assert "'b.jpg'" in message
    assert PHOTO not in message  # the real photo isn't listed
    assert garment_count(db_path) == 0


def test_hidden_characters_are_visible_in_the_message(db_path, monkeypatch, capsys):
    # The CRLF incident: a trailing \r made every path look fine when printed
    message = run_add_expecting_error(monkeypatch, capsys, "-t", PHOTO + "\r")

    assert "\\r" in message  # shown as the two characters \ and r, not a hidden carriage return


def test_a_directory_is_not_a_photo(db_path, monkeypatch, capsys, tmp_path):
    folder = tmp_path / "not_a_photo"
    folder.mkdir()

    message = run_add_expecting_error(monkeypatch, capsys, "-t", str(folder))

    assert str(folder) in message
    assert garment_count(db_path) == 0


def test_urls_are_not_checked_as_paths(db_path, monkeypatch, capsys):
    # The missing path stops the run before staging, so the URL is never downloaded
    message = run_add_expecting_error(monkeypatch, capsys, "-t", "https://example.com/shirt.jpg", "nope.jpg")

    assert "example.com" not in message
    assert "'nope.jpg'" in message


# --- good input still works ---------------------------------------------------

def test_real_photo_is_added(db_path, monkeypatch):
    assert run_add(monkeypatch, "-t", PHOTO) == 0
    assert garment_count(db_path) == 1


def test_test_mode_without_photos_still_works(db_path, monkeypatch):
    assert run_add(monkeypatch, "-t") == 0
    assert garment_count(db_path) == 1

# tests/test_outfit_command.py
# How `enclothed outfit` parses -w. get_outfits is replaced with a fake that
# records the anchors it receives, so no Claude call, log write or DB write happens.
import sys

import pytest

from enclothed import config, db, main as main_module
from enclothed.intake import TEST_GARMENT
from enclothed.main import main
from enclothed.outfit import TEST_OUTFITS


@pytest.fixture
def received(tmp_path, monkeypatch):
    """A temp DB with 3 garments (ids 1, 2, 3), config pointed at tmp_path, and a
    fake get_outfits. Returns a dict that will hold the anchors main() passed in."""
    path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(config, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(config, "INTAKE_DIR", tmp_path / "intake")
    monkeypatch.setattr(config, "OUTFIT_LOG_PATH", tmp_path / "outfit_log.jsonl")
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    for _ in range(3):
        db.insert_garment(path, TEST_GARMENT.model_copy())

    calls = {}

    def fake_get_outfits(db_path, wardrobe, anchors, *rest):
        calls["anchors"] = anchors
        return TEST_OUTFITS

    # Patch the name main.py imported, not enclothed.outfit.get_outfits.
    monkeypatch.setattr(main_module, "get_outfits", fake_get_outfits)
    return calls


def run_outfit(monkeypatch, *cli_args):
    monkeypatch.setattr(sys, "argv", ["enclothed", "outfit", "-t", *cli_args])
    return main()


def test_with_takes_several_ids_after_one_flag(monkeypatch, received):
    run_outfit(monkeypatch, "-w", "1", "2")
    assert received["anchors"] == [1, 2]


def test_with_can_still_be_repeated(monkeypatch, received):
    run_outfit(monkeypatch, "-w", "1", "-w", "2")
    assert received["anchors"] == [1, 2]


def test_with_mixed_forms_give_one_flat_list(monkeypatch, received):
    # action="append" would give [[1, 2], [3]]; extend flattens.
    run_outfit(monkeypatch, "-w", "1", "2", "-w", "3")
    assert received["anchors"] == [1, 2, 3]


def test_with_stops_at_the_next_flag(monkeypatch, received):
    run_outfit(monkeypatch, "-w", "1", "2", "-p", "dinner")
    assert received["anchors"] == [1, 2]


def test_no_with_means_no_anchors(monkeypatch, received):
    run_outfit(monkeypatch, "-p", "dinner")
    assert received["anchors"] is None


def test_bare_with_is_an_error(monkeypatch, capsys, received):
    # nargs="+": -w with no id is a usage error (exit 2), not "no anchors".
    with pytest.raises(SystemExit) as exc_info:
        run_outfit(monkeypatch, "-w", "-p", "dinner")
    assert exc_info.value.code == 2
    assert "expected at least one argument" in capsys.readouterr().err
    assert "anchors" not in received

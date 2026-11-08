# tests/test_evals.py
# eval-outfits in test mode: canned outfits, no client, no tokens. Checks the files it writes
# and that the real database is left alone.
import json
import sqlite3
from contextlib import closing

import pytest

from enclothed import config, db, evals
from enclothed.intake import TEST_GARMENT


@pytest.fixture
def owner_db(tmp_path):
    path = tmp_path / "enclothed.db"
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    db.insert_garment(path, 1, TEST_GARMENT.model_copy())
    return path


def requests_file(tmp_path, requests):
    path = tmp_path / "requests.json"
    path.write_text(json.dumps({"requests": requests}), encoding="utf-8")
    return path


def outfit_count(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM outfits").fetchone()[0]


def test_writes_prompt_results_and_scores(tmp_path, owner_db):
    reqs = requests_file(tmp_path, [{"id": "a", "details": "dinner"}, {"id": "b", "details": "office", "riskiness": "bold", "count": 2}])
    out = evals.run("v1", 2, 1, owner_db, reqs, None, True, tmp_path / "evals")
    rows = [json.loads(line) for line in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(r["request_id"], r["run"]) for r in rows] == [("a", 1), ("a", 2), ("b", 1), ("b", 2)]
    assert rows[2]["options"] == "2 bold"
    assert len({r["prompt_hash"] for r in rows}) == 1
    assert "You suggest outfits" in (out / "prompt.txt").read_text(encoding="utf-8")
    scores = (out / "scores.md").read_text(encoding="utf-8")
    assert "| a | 1 | 1 | safe |" in scores
    assert "### b, run 2" in scores
    assert out.name.endswith("_v1")


def test_leaves_the_real_database_alone(tmp_path, owner_db):
    before = owner_db.read_bytes()
    evals.run("v1", 1, 1, owner_db, requests_file(tmp_path, [{"id": "a", "details": "dinner"}]), None, True, tmp_path / "evals")
    assert owner_db.read_bytes() == before
    assert outfit_count(owner_db) == 0


def test_only_runs_the_named_requests(tmp_path, owner_db):
    reqs = requests_file(tmp_path, [{"id": "a", "details": "x"}, {"id": "b", "details": "y"}])
    out = evals.run("v1", 1, 1, owner_db, reqs, ["b"], True, tmp_path / "evals")
    assert [json.loads(l)["request_id"] for l in (out / "results.jsonl").read_text().splitlines()] == ["b"]


@pytest.mark.parametrize("requests, only, message", [
    ([{"id": "a", "details": "x"}, {"id": "a", "details": "y"}], None, "unique"),
    ([{"id": "a", "details": "x"}], ["zzz"], "No request with id"),
    ([{"id": "a", "details": "x", "count": 9}], None, "count must be"),
])
def test_bad_requests_fail_before_any_call(tmp_path, owner_db, requests, only, message):
    with pytest.raises(ValueError, match=message):
        evals.run("v1", 1, 1, owner_db, requests_file(tmp_path, requests), only, True, tmp_path / "evals")
    assert not (tmp_path / "evals").exists()


def test_the_shipped_requests_file_is_valid():
    assert len(evals.load_requests(evals.REQUESTS_PATH, None)) >= 5

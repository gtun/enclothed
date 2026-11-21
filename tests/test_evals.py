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


# --- comparing providers --------------------------------------------------------------------

def rows_of(out):
    return [json.loads(line) for line in (out / "results.jsonl").read_text(encoding="utf-8").splitlines()]


def one_request(tmp_path):
    return requests_file(tmp_path, [{"id": "a", "details": "dinner"}])


def test_each_row_and_the_scores_name_the_provider_and_model(tmp_path, owner_db):
    out = evals.run("v1", 1, 1, owner_db, one_request(tmp_path), None, True, tmp_path / "evals")
    [row] = rows_of(out)
    assert (row["provider"], row["model"]) == ("anthropic", config.MODELS_BY_PROVIDER["anthropic"]["outfits"])
    assert f"on `{row['model']}` (anthropic)" in (out / "scores.md").read_text(encoding="utf-8")


def test_the_provider_setting_is_recorded(tmp_path, owner_db, monkeypatch):
    monkeypatch.setenv("ENCLOTHED_LLM_PROVIDER", "openai")
    [row] = rows_of(evals.run("v1", 1, 1, owner_db, one_request(tmp_path), None, True, tmp_path / "evals"))
    assert (row["provider"], row["model"]) == ("openai", config.MODELS_BY_PROVIDER["openai"]["outfits"])


def run_main(monkeypatch, tmp_path, owner_db, *flags):
    monkeypatch.setattr(evals, "load_dotenv", lambda: None)   # never the real .env
    monkeypatch.setattr(evals, "EVALS_DIR", tmp_path / "evals")
    monkeypatch.setenv("ENCLOTHED_LLM_PROVIDER", "anthropic")   # so monkeypatch undoes what --provider sets
    monkeypatch.setattr("sys.argv", ["eval-outfits", "-l", "cmp", "-t", "--runs", "1", "--db", str(owner_db),
                                     "--requests", str(one_request(tmp_path)), *flags])
    evals.main()
    [out] = (tmp_path / "evals").iterdir()
    return rows_of(out)


def test_the_provider_flag_runs_on_that_provider(tmp_path, owner_db, monkeypatch):
    [row] = run_main(monkeypatch, tmp_path, owner_db, "--provider", "openai")
    assert row["provider"] == "openai"


def test_the_model_flag_applies_to_the_chosen_provider(tmp_path, owner_db, monkeypatch):
    monkeypatch.setitem(config.MODELS_BY_PROVIDER["openai"], "outfits", config.MODELS_BY_PROVIDER["openai"]["outfits"])
    [row] = run_main(monkeypatch, tmp_path, owner_db, "--provider", "openai", "--model", "gpt-other")
    assert (row["provider"], row["model"]) == ("openai", "gpt-other")
    assert config.MODELS_BY_PROVIDER["anthropic"]["outfits"] != "gpt-other"


def test_an_unknown_provider_is_refused(tmp_path, owner_db, monkeypatch):
    with pytest.raises(SystemExit):
        run_main(monkeypatch, tmp_path, owner_db, "--provider", "gemini")


def test_the_cost_adds_up_priced_calls_only():
    usage = lambda model: {"model": model, "input_tokens": 1_000_000, "output_tokens": 0}
    rows = [{"usage": usage("gpt-6.1-terra")}, {"usage": usage("unpriced-model")}, {"usage": None}]
    assert evals.total_cost(rows) == pytest.approx(config.MODEL_PRICES["gpt-6.1-terra"]["input"])
    assert evals.total_cost([{"usage": None}]) is None

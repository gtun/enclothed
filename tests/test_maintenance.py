import sqlite3
from datetime import date, timedelta

import pytest

from enclothed import config, maintenance
from enclothed.maintenance import snapshots_to_keep

WEDNESDAY = date(2026, 11, 4)


def days_back(count: int) -> list[date]:
    return [WEDNESDAY - timedelta(days=i) for i in range(count)]


def test_keeps_everything_when_under_the_limits():
    days = days_back(3)
    assert snapshots_to_keep(days) == set(days)


def test_keeps_seven_newest_and_four_newest_sundays():
    kept = snapshots_to_keep(days_back(60))
    newest_seven = set(days_back(7))
    sundays = {date(2026, 11, 1), date(2026, 10, 25), date(2026, 10, 18), date(2026, 10, 11)}
    assert kept == newest_seven | sundays


def test_keep_does_not_depend_on_input_order():
    days = days_back(60)
    assert snapshots_to_keep(list(reversed(days))) == snapshots_to_keep(days)


@pytest.fixture
def live_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "enclothed.db")
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
    conn.close()
    return config.DB_PATH


def test_snapshot_makes_a_readable_copy_and_no_partial(live_db):
    maintenance.snapshot()
    files = list(config.SNAPSHOTS_DIR.iterdir())
    assert [f.name for f in files] == [f"enclothed-{date.today().isoformat()}.db"]
    conn = sqlite3.connect(files[0])
    assert conn.execute("SELECT x FROM t").fetchall() == [(1,)]
    conn.close()


def test_snapshot_prunes_old_files(live_db):
    config.SNAPSHOTS_DIR.mkdir()
    old = config.SNAPSHOTS_DIR / "enclothed-2020-01-01.db"   # a Wednesday, older than 7 newer files
    old.touch()
    for i in range(1, 8):
        (config.SNAPSHOTS_DIR / f"enclothed-{(date.today() - timedelta(days=i)).isoformat()}.db").touch()
    maintenance.snapshot()
    assert not old.exists()


def test_snapshot_missing_db_stops_without_creating_one(live_db):
    live_db.unlink()
    with pytest.raises(SystemExit):
        maintenance.snapshot()
    assert not live_db.exists()

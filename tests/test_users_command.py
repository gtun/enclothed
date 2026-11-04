import sys

import pytest

from enclothed import config, db, main


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "GARMENTS_DIR", tmp_path / "garments")
    monkeypatch.setattr(config, "INTAKE_DIR", tmp_path / "intake")

    def run_command(*args):
        monkeypatch.setattr(sys, "argv", ["enclothed", *args])
        return main.main()
    return run_command


def test_adduser_creates_a_regular_user(run):
    assert run("adduser", "kim", "Kim@Example.com") == 0
    user = db.select_user_by_email(config.DB_PATH, "kim@example.com")
    assert (user.username, user.is_admin) == ("kim", False)


def test_adduser_admin_flag(run):
    run("adduser", "kim", "kim@example.com", "--admin")
    assert db.select_user_by_username(config.DB_PATH, "kim").is_admin


@pytest.mark.parametrize("username, email", [("kim", "other@example.com"), ("other", "KIM@example.com")])
def test_adduser_rejects_a_duplicate(run, username, email):
    run("adduser", "kim", "kim@example.com")
    with pytest.raises(SystemExit):
        run("adduser", username, email)


def test_edituser_changes_only_what_you_pass(run):
    run("edituser", "1", "-e", "Me@Example.com")
    user = db.select_user(config.DB_PATH, 1)
    assert (user.username, user.email) == ("owner", "me@example.com")


def test_edituser_unknown_id_stops(run):
    with pytest.raises(SystemExit):
        run("edituser", "99", "-u", "x")


def test_users_lists_everyone(run, capsys):
    run("adduser", "kim", "kim@example.com")
    capsys.readouterr()
    run("users")
    output = capsys.readouterr().out
    assert "owner" in output and "kim@example.com" in output

# tests/conftest.py
import pytest

from enclothed import api


@pytest.fixture(autouse=True)
def private_weigh_log(tmp_path, monkeypatch):
    """Every test gets its own weigh log, so the usage tests never read a real one in data/."""
    monkeypatch.setattr(api, "WEIGH_LOG_PATH", tmp_path / "weigh_log.jsonl")

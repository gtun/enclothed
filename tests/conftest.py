# tests/conftest.py
from pathlib import Path

import pytest

from enclothed import api, config

# Every path in config under data/ or backups/, as config first had it. The app reads these as config.NAME when
# it uses them, so patching config moves them for every module at once.
REAL_DATA_DIR, REAL_BACKUPS_DIR = config.DATA_DIR, config.BACKUPS_DIR
REAL_DATA_PATHS = {name: value for name, value in vars(config).items()
                   if isinstance(value, Path) and (value.is_relative_to(REAL_DATA_DIR) or value.is_relative_to(REAL_BACKUPS_DIR))}


@pytest.fixture(autouse=True)
def private_data(tmp_path, monkeypatch):
    """Every test gets its own data folder: data/ becomes tmp_path, and backups/ becomes tmp_path/backups. So the
    database, photos, logs, shares and reworks a test touches are its own, and none of them land in data/."""
    for name, real in REAL_DATA_PATHS.items():
        if real.is_relative_to(REAL_DATA_DIR):
            moved = tmp_path / real.relative_to(REAL_DATA_DIR)
        else:
            moved = tmp_path / "backups" / real.relative_to(REAL_BACKUPS_DIR)
        monkeypatch.setattr(config, name, moved)
    leaked = [str(p) for p in api._usage_logs().values() if not p.is_relative_to(tmp_path)]
    assert not leaked, f"_usage_logs() still points outside tmp_path, so tests would read data/: {leaked}"


@pytest.fixture(autouse=True)
def default_provider(monkeypatch):
    """api.py loads .env, so a provider chosen there would reach every test. Tests that want one set it themselves."""
    monkeypatch.delenv("ENCLOTHED_LLM_PROVIDER", raising=False)

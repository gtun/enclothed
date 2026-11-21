# tests/conftest.py
from pathlib import Path

import pytest

from enclothed import api, config

# The names in api (and config) of every log the usage page reads, found from _usage_logs itself so a log
# added there later is covered without touching this file.
USAGE_LOG_NAMES = [name for name, value in vars(api).items()
                   if isinstance(value, Path) and value in api._usage_logs().values()]


@pytest.fixture(autouse=True)
def private_logs(tmp_path, monkeypatch):
    """Every test gets its own LLM logs, so the usage tests never read a real one in data/,
    and its own folder for share links' photos, so none land in data/."""
    for name in USAGE_LOG_NAMES:
        path = tmp_path / f"{name.lower()}.jsonl"
        monkeypatch.setattr(api, name, path)
        if hasattr(config, name):   # the CLI reads them from config
            monkeypatch.setattr(config, name, path)
    leaked = [str(p) for p in api._usage_logs().values() if not p.is_relative_to(tmp_path)]
    assert not leaked, f"_usage_logs() still points outside tmp_path, so tests would read data/: {leaked}"
    monkeypatch.setattr(api, "SHARES_DIR", tmp_path / "thumbs" / "shares")


@pytest.fixture(autouse=True)
def default_provider(monkeypatch):
    """api.py loads .env, so a provider chosen there would reach every test. Tests that want one set it themselves."""
    monkeypatch.delenv("ENCLOTHED_LLM_PROVIDER", raising=False)

import importlib
import pkgutil
from pathlib import Path

import enclothed
from enclothed import config

from conftest import REAL_DATA_PATHS


def test_every_data_path_is_moved_under_tmp_path(tmp_path):
    for name in REAL_DATA_PATHS:
        assert getattr(config, name).is_relative_to(tmp_path), name


def test_no_module_keeps_its_own_copy_of_a_data_path():
    """Paths are read as config.NAME when used. A module that imports one by name holds the real path, which
    patching config doesn't reach, so its tests would write to data/."""
    real = {value: name for name, value in REAL_DATA_PATHS.items()}
    copies = []
    for module_info in pkgutil.iter_modules(enclothed.__path__):
        if module_info.name == "config":
            continue
        module = importlib.import_module(f"enclothed.{module_info.name}")
        copies += [f"{module_info.name}.{attr} ({real[value]})" for attr, value in vars(module).items()
                   if isinstance(value, Path) and value in real]
    assert not copies, f"Read these as config.NAME instead: {copies}"

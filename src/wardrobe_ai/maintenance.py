import shutil
from wardrobe_ai import config

GOLDEN = config.BACKUPS_DIR / "golden"   # make_archive adds ".tar.gz"


def backup() -> None:
    if not config.DATA_DIR.exists():
        raise SystemExit(f"Nothing to back up: {config.DATA_DIR} doesn't exist")
    config.BACKUPS_DIR.mkdir(exist_ok=True)
    archive = shutil.make_archive(str(GOLDEN), "gztar", root_dir=config.PROJECT_ROOT, base_dir="data")
    print(f"Backed up data/ to {archive}")


def restore() -> None:
    archive = GOLDEN.with_name(GOLDEN.name + ".tar.gz")
    if not archive.exists():
        raise SystemExit(f"No backup found at {archive}")
    shutil.rmtree(config.DATA_DIR, ignore_errors=True)
    shutil.unpack_archive(archive, extract_dir=config.PROJECT_ROOT)
    print(f"Restored data/ from {archive}")


def refresh() -> None:
    shutil.rmtree(config.DATA_DIR, ignore_errors=True)
    print(f"Deleted {config.DATA_DIR}")
    
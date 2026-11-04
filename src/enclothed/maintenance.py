import shutil
import sqlite3
from contextlib import closing
from datetime import date
from enclothed import config

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


def snapshots_to_keep(days: list[date], daily: int = 7, weekly: int = 4) -> set[date]:
    newest_first = sorted(days, reverse=True)
    sundays = [d for d in newest_first if d.weekday() == 6]
    return set(newest_first[:daily]) | set(sundays[:weekly])


def snapshot() -> None:
    if not config.DB_PATH.exists():
        raise SystemExit(f"Nothing to snapshot: {config.DB_PATH} doesn't exist")
    config.SNAPSHOTS_DIR.mkdir(exist_ok=True)
    final = config.SNAPSHOTS_DIR / f"enclothed-{date.today().isoformat()}.db"
    partial = final.with_suffix(".partial")
    partial.unlink(missing_ok=True)

    source_uri = f"file:{config.DB_PATH}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source, closing(sqlite3.connect(partial)) as dest:
        source.backup(dest)
        result = dest.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        partial.unlink()
        raise SystemExit(f"Snapshot failed integrity check: {result}")
    partial.replace(final)

    days = {date.fromisoformat(p.stem.removeprefix("enclothed-")): p
            for p in config.SNAPSHOTS_DIR.glob("enclothed-*.db")}
    keep = snapshots_to_keep(list(days))
    for day, path in days.items():
        if day not in keep:
            path.unlink()
    print(f"Saved {final}; keeping {len(keep)} snapshots")

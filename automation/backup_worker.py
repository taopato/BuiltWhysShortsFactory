from __future__ import annotations

import argparse
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from control_center_store import ControlCenterStore
from review_queue import DEFAULT_DB


ROOT = Path(__file__).resolve().parents[1]


def backup(db_path: Path) -> Path:
    directory = ROOT / "storage" / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"control-center-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.sqlite3"
    source = sqlite3.connect(db_path)
    destination = sqlite3.connect(output)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    backups = sorted(directory.glob("control-center-*.sqlite3"), reverse=True)
    for old in backups[14:]:
        old.unlink(missing_ok=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=86400)
    args = parser.parse_args()
    while True:
        store = ControlCenterStore(args.db)
        try:
            output = backup(args.db)
            store.heartbeat("backup-worker", detail=output.name)
            store.event("info", "backup_complete", f"Database backup created: {output.name}")
        except Exception as exc:
            store.heartbeat("backup-worker", "error", str(exc))
            store.event("error", "backup_failed", str(exc))
        finally:
            store.close()
        if args.once:
            return 0
        time.sleep(max(3600, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())

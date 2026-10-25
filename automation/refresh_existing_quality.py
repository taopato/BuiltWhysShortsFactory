from __future__ import annotations

import argparse
from pathlib import Path

from control_center_store import ControlCenterStore
from review_queue import DEFAULT_DB


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    store = ControlCenterStore(args.db)
    try:
        rows = store.connection.execute(
            """SELECT id FROM jobs WHERE status IN
               ('pending_review','approved','publish_pending','published')"""
        ).fetchall()
        for row in rows:
            report = store.refresh_quality(str(row["id"]))
            print(row["id"], report["status"], report["score"])
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

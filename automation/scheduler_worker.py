from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from candidate_planner import load_catalog
from control_center_store import ControlCenterStore
from notifier import notify
from review_queue import DEFAULT_DB


def tick(store: ControlCenterStore) -> None:
    created = store.ensure_schedule_horizon()
    assigned = store.auto_assign() if store.setting("auto_fill_schedule", "true") == "true" else 0
    reserve = store.connection.execute(
        "SELECT COUNT(*) count FROM jobs WHERE status='approved' AND is_reserve=1"
    ).fetchone()["count"]
    minimum = int(store.setting("reserve_minimum", "6"))
    if reserve < minimum:
        last = store.connection.execute(
            "SELECT created_at FROM events WHERE kind='reserve_low' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        stale = not last or datetime.fromisoformat(last["created_at"]) < (
            datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=12)
        )
        if stale:
            message = f"Onaylı yedek havuzu düşük: {reserve}/{minimum}"
            store.event("warning", "reserve_low", message)
            notify(message, "warning")
    visual_active = bool(load_catalog().get("visualwhys", {}).get("active", False))
    visual_reserve = store.connection.execute(
        """SELECT COUNT(*) count FROM jobs
           WHERE channel_key='visualwhys' AND status='approved' AND is_reserve=1"""
    ).fetchone()["count"] if visual_active else 0
    visual_minimum = 3 if visual_active else 0
    if visual_active and visual_reserve < visual_minimum:
        last = store.connection.execute(
            """SELECT created_at FROM events WHERE kind='visual_reserve_low'
               ORDER BY created_at DESC LIMIT 1"""
        ).fetchone()
        stale = not last or datetime.fromisoformat(last["created_at"]) < (
            datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=12)
        )
        if stale:
            message = f"Görsel Bulmacalar onaylı yedeği düşük: {visual_reserve}/{visual_minimum}"
            store.event("warning", "visual_reserve_low", message, channel="visualwhys")
            notify(message, "warning")
    store.heartbeat(
        "scheduler-worker",
        detail=f"slots+{created}, assigned+{assigned}, reserve={reserve}, visual={visual_reserve}/{visual_minimum}",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()
    while True:
        store = ControlCenterStore(args.db)
        try:
            tick(store)
        except Exception as exc:
            store.heartbeat("scheduler-worker", "error", str(exc))
            store.event("error", "scheduler_worker", str(exc))
        finally:
            store.close()
        if args.once:
            return 0
        time.sleep(max(15, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())

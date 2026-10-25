from __future__ import annotations

import argparse
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from control_center_store import ControlCenterStore
from notifier import notify
from review_queue import DEFAULT_DB


ROOT = Path(__file__).resolve().parents[1]


def check(store: ControlCenterStore) -> None:
    failures = []
    for name, url in (
        ("render-api", "http://api:8080/docs"),
        ("control-center", "http://control-center:8090/healthz"),
    ):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code >= 500:
                raise RuntimeError(f"HTTP {response.status_code}")
            store.heartbeat(name)
        except Exception as exc:
            store.heartbeat(name, "error", str(exc))
            failures.append(f"{name}: {exc}")
    disk = shutil.disk_usage(ROOT)
    percent = disk.used * 100 / disk.total
    if percent >= 85:
        failures.append(f"disk usage %{percent:.1f}")
    if failures:
        message = "Sistem sağlık uyarısı: " + "; ".join(failures)
        last = store.connection.execute(
            "SELECT created_at FROM events WHERE kind='health_alert' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        should_alert = not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last["created_at"])).total_seconds() > 1800
        if should_alert:
            store.event("error", "health_alert", message)
            notify(message, "error")
    store.heartbeat("health-monitor", detail=f"disk={percent:.1f}%")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()
    while True:
        store = ControlCenterStore(args.db)
        try:
            check(store)
        finally:
            store.close()
        if args.once:
            return 0
        time.sleep(max(30, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())

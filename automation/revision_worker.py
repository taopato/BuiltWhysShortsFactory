from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from review_queue import ApprovalQueue, DEFAULT_DB, QueueError


ROOT_DIR = Path(__file__).resolve().parents[1]
AUTOMATION_DIR = ROOT_DIR / "automation"


def run_checked(command: list[str]) -> None:
    process = subprocess.run(command, cwd=ROOT_DIR, text=True)
    if process.returncode != 0:
        raise QueueError(f"command failed with exit code {process.returncode}: {command[0]}")


def process_visual_revision(queue: ApprovalQueue, job: dict) -> None:
    manifest_path = Path(job["manifest_path"])
    pilot_dir = manifest_path.parent
    if not pilot_dir.is_dir() or pilot_dir.parent.name != "pilots":
        raise QueueError(f"cannot determine pilot directory from {manifest_path}")
    pilot_name = pilot_dir.name
    print(f"Refreshing Pexels visuals for {job['id']} ({pilot_name})", flush=True)
    if os.environ.get("PEXELS_API_KEY"):
        run_checked(
            [sys.executable, str(AUTOMATION_DIR / "generate_pexels_batch.py"),
             "--pilot", pilot_name, "--force"]
        )
    else:
        run_checked(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(AUTOMATION_DIR / "run_pexels_assets.ps1"),
                "-Pilot", pilot_name, "-Force",
            ]
        )
    run_checked(
        [
            sys.executable,
            str(AUTOMATION_DIR / "render_job.py"),
            job["id"],
            "--pilot-dir", str(pilot_dir),
        ]
    )
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        run_checked([sys.executable, str(AUTOMATION_DIR / "review_queue.py"), "send", job["id"]])
    else:
        run_checked(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(AUTOMATION_DIR / "run_telegram.ps1"),
                "-Mode", "send", "-JobId", job["id"],
            ]
        )


def process_once(db_path: Path) -> bool:
    queue = ApprovalQueue(db_path)
    try:
        jobs = queue.list_jobs("revision_requested")
        visual_job = next((job for job in reversed(jobs) if job["review_action"] == "visuals"), None)
        if visual_job is None:
            return False
        try:
            process_visual_revision(queue, visual_job)
        except Exception as exc:
            current = queue.get_job(visual_job["id"])
            if current["status"] == "revision_requested":
                queue.mark_failed(visual_job["id"], str(exc))
            raise
        return True
    finally:
        queue.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Process BuiltWhys Telegram revision requests")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    print("BuiltWhys revision worker is running.", flush=True)
    while True:
        try:
            processed = process_once(args.db)
        except Exception as exc:
            print(f"revision worker error: {exc}", file=sys.stderr, flush=True)
            processed = True
        if args.once:
            return 0
        if not processed:
            time.sleep(max(3, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())

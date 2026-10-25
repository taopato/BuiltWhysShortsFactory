from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

import requests

from control_center_store import ControlCenterStore
from google_auth import headers
from notifier import notify
from review_queue import DEFAULT_DB, utc_now


ROOT = Path(__file__).resolve().parents[1]


def ensure_table(store: ControlCenterStore) -> None:
    store.connection.execute(
        """CREATE TABLE IF NOT EXISTS drive_archives(
        job_id TEXT PRIMARY KEY, folder_id TEXT NOT NULL DEFAULT '', video_file_id TEXT NOT NULL DEFAULT '',
        metadata_file_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL)"""
    )
    store.connection.commit()


def create_folder(name: str, parent: str) -> str:
    metadata: dict[str, Any] = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent:
        metadata["parents"] = [parent]
    response = requests.post(
        "https://www.googleapis.com/drive/v3/files",
        params={"fields": "id"}, headers={**headers(), "Content-Type": "application/json"},
        json=metadata, timeout=60,
    )
    response.raise_for_status()
    return str(response.json()["id"])


def upload(path: Path, name: str, parent: str, mime: str | None = None) -> str:
    boundary = "builtwhys_" + uuid.uuid4().hex
    metadata = json.dumps({"name": name, "parents": [parent]}).encode()
    content = path.read_bytes()
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + metadata
        + f"\r\n--{boundary}\r\nContent-Type: {mime or mimetypes.guess_type(name)[0] or 'application/octet-stream'}\r\n\r\n".encode()
        + content + f"\r\n--{boundary}--\r\n".encode()
    )
    response = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files",
        params={"uploadType": "multipart", "fields": "id"},
        headers={**headers(), "Content-Type": f"multipart/related; boundary={boundary}"}, data=body, timeout=1200,
    )
    response.raise_for_status()
    return str(response.json()["id"])


def archive(store: ControlCenterStore, job: dict[str, Any]) -> None:
    root_folder = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip() or store.setting("google_drive_folder_id")
    if not root_folder:
        root_folder = create_folder("BuiltWhys Archive", "")
        store.set_setting("google_drive_folder_id", root_folder)
    folder = create_folder(f"{job['id']}-{job.get('language','en-US')}", root_folder)
    package_path = ROOT / "storage" / "archives" / f"{job['id']}-metadata.json"
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package = dict(job)
    package.pop("video_path", None)
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    video_id = upload(Path(job["video_path"]), f"{job['id']}-master.mp4", folder, "video/mp4")
    metadata_id = upload(package_path, "metadata.json", folder, "application/json")
    for field, target in (("manifest_path", "sources.json"), ("metadata_path", "social_metadata.json"),
                          ("thumbnail_path", "thumbnail.jpg")):
        candidate = Path(job.get(field) or "")
        if candidate.is_file():
            upload(candidate, target, folder)
    store.connection.execute(
        """INSERT INTO drive_archives(job_id,folder_id,video_file_id,metadata_file_id,status,updated_at)
           VALUES (?,?,?,?, 'archived', ?) ON CONFLICT(job_id) DO UPDATE SET folder_id=excluded.folder_id,
           video_file_id=excluded.video_file_id,metadata_file_id=excluded.metadata_file_id,status='archived',
           error='',updated_at=excluded.updated_at""",
        (job["id"], folder, video_id, metadata_id, utc_now()),
    )
    store.connection.commit()
    store.event("info", "drive_archived", "Published video archived to Google Drive", job["id"], folder_id=folder)


def process_once(store: ControlCenterStore) -> bool:
    ensure_table(store)
    row = store.connection.execute(
        """SELECT j.* FROM jobs j LEFT JOIN drive_archives d ON d.job_id=j.id
           WHERE j.status='published' AND (d.status IS NULL OR d.status='failed')
           ORDER BY j.published_at LIMIT 1"""
    ).fetchone()
    if not row:
        return False
    job = store.job(row["id"])
    try:
        archive(store, job)
    except Exception as exc:
        store.connection.execute(
            """INSERT INTO drive_archives(job_id,status,error,updated_at) VALUES (?,'failed',?,?)
               ON CONFLICT(job_id) DO UPDATE SET status='failed',error=excluded.error,updated_at=excluded.updated_at""",
            (job["id"], str(exc)[:2000], utc_now()),
        )
        store.connection.commit()
        raise
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=300)
    args = parser.parse_args()
    while True:
        store = ControlCenterStore(args.db)
        try:
            google_ready = all(os.environ.get(key, "").strip() for key in (
                "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"
            ))
            if google_ready:
                store.heartbeat("drive-archive-worker")
                processed = process_once(store)
            else:
                store.heartbeat("drive-archive-worker", "disabled", "Google OAuth is not configured")
                processed = False
        except Exception as exc:
            store.heartbeat("drive-archive-worker", "error", str(exc))
            store.event("error", "drive_archive", str(exc))
            processed = False
            if args.once:
                return 2
        finally:
            store.close()
        if args.once:
            return 0
        if not processed:
            time.sleep(max(60, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())

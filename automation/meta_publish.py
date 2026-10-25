from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import requests

from review_queue import DEFAULT_DB, ApprovalQueue, QueueError, validate_render


ROOT_DIR = Path(__file__).resolve().parents[1]


class MetaError(RuntimeError):
    pass


class MetaPublisher:
    def __init__(self, language: str = "en-US") -> None:
        suffix = "_TR" if language == "tr-TR" else ""
        self.token = os.environ.get(f"META_PAGE_ACCESS_TOKEN{suffix}", "")
        self.page_id = os.environ.get(f"META_PAGE_ID{suffix}", "")
        self.ig_user_id = os.environ.get(f"META_IG_USER_ID{suffix}", "")
        self.version = os.environ.get("META_GRAPH_VERSION", "v25.0")
        if not all((self.token, self.page_id, self.ig_user_id)):
            raise MetaError("Meta credentials are missing; use automation/run_meta.ps1")
        self.graph = f"https://graph.facebook.com/{self.version}"

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise MetaError(f"Meta returned HTTP {response.status_code} without JSON") from exc
        if not response.ok or payload.get("error"):
            error = payload.get("error") or payload
            raise MetaError(f"Meta API error (HTTP {response.status_code}): {error}")
        return payload

    def verify(self) -> dict[str, Any]:
        response = requests.get(
            f"{self.graph}/{self.page_id}",
            params={"fields": "id,name,instagram_business_account{id,username}"},
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30,
        )
        payload = self._json(response)
        return {
            "facebook_page": {"id": payload.get("id"), "name": payload.get("name")},
            "instagram": payload.get("instagram_business_account"),
            "connected": True,
        }

    def publish_facebook(self, video_path: Path, caption: str) -> str:
        start = self._json(
            requests.post(
                f"{self.graph}/{self.page_id}/video_reels",
                data={"upload_phase": "start", "access_token": self.token},
                timeout=30,
            )
        )
        video_id = str(start["video_id"])
        upload_url = start.get("upload_url") or (
            f"https://rupload.facebook.com/video-upload/{self.version}/{video_id}"
        )
        with video_path.open("rb") as video:
            upload = requests.post(
                upload_url,
                data=video,
                headers={
                    "Authorization": f"OAuth {self.token}",
                    "offset": "0",
                    "file_size": str(video_path.stat().st_size),
                    "Content-Type": "application/octet-stream",
                },
                timeout=600,
            )
        self._json(upload)
        self._json(
            requests.post(
                f"{self.graph}/{self.page_id}/video_reels",
                data={
                    "upload_phase": "finish",
                    "video_id": video_id,
                    "video_state": "PUBLISHED",
                    "description": caption,
                    "access_token": self.token,
                },
                timeout=60,
            )
        )
        return video_id

    def publish_instagram(self, video_path: Path, caption: str) -> str:
        container = self._json(
            requests.post(
                f"{self.graph}/{self.ig_user_id}/media",
                data={
                    "media_type": "REELS",
                    "upload_type": "resumable",
                    "caption": caption,
                    "share_to_feed": "true",
                    "access_token": self.token,
                },
                timeout=60,
            )
        )
        container_id = str(container["id"])
        upload_url = container.get("uri") or (
            f"https://rupload.facebook.com/ig-api-upload/{self.version}/{container_id}"
        )
        with video_path.open("rb") as video:
            upload = requests.post(
                upload_url,
                data=video,
                headers={
                    "Authorization": f"OAuth {self.token}",
                    "offset": "0",
                    "file_size": str(video_path.stat().st_size),
                    "Content-Type": "application/octet-stream",
                },
                timeout=600,
            )
        self._json(upload)

        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            status = self._json(
                requests.get(
                    f"{self.graph}/{container_id}",
                    params={"fields": "status_code,status", "access_token": self.token},
                    timeout=30,
                )
            )
            code = status.get("status_code")
            if code == "FINISHED":
                break
            if code in {"ERROR", "EXPIRED"}:
                raise MetaError(f"Instagram processing failed: {status}")
            time.sleep(5)
        else:
            raise MetaError("Instagram processing did not finish within 5 minutes")

        published = self._json(
            requests.post(
                f"{self.graph}/{self.ig_user_id}/media_publish",
                data={"creation_id": container_id, "access_token": self.token},
                timeout=60,
            )
        )
        return str(published["id"])


def load_metadata(path: Path) -> dict[str, Any]:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MetaError(f"invalid social metadata file: {exc}") from exc
    caption = str(metadata.get("caption", "")).strip()
    if not caption:
        raise MetaError("social metadata requires a caption")
    if len(caption) > 2200:
        raise MetaError("social caption exceeds 2200 characters")
    return metadata


def ensure_publication_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_publications (
            job_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            status TEXT NOT NULL,
            remote_id TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(job_id, platform)
        )
        """
    )
    connection.commit()


def record(connection: sqlite3.Connection, job_id: str, platform: str, status: str,
           remote_id: str = "", error: str = "") -> None:
    connection.execute(
        """
        INSERT INTO meta_publications(job_id, platform, status, remote_id, error, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(job_id, platform) DO UPDATE SET
            status=excluded.status, remote_id=excluded.remote_id,
            error=excluded.error, updated_at=CURRENT_TIMESTAMP
        """,
        (job_id, platform, status, remote_id, error),
    )
    connection.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish approved BuiltWhys videos to Meta")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify")
    publish = subparsers.add_parser("publish")
    publish.add_argument("job_id")
    publish.add_argument("--platform", choices=("facebook", "instagram", "both"), default="both")
    publish.add_argument("--metadata", type=Path)
    publish.add_argument("--db", type=Path, default=DEFAULT_DB)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        publisher = MetaPublisher()
        if args.command == "verify":
            print(json.dumps(publisher.verify(), ensure_ascii=False, indent=2))
            return 0

        queue = ApprovalQueue(args.db)
        try:
            job = queue.get_job(args.job_id)
            if job["status"] != "approved":
                raise MetaError("only Telegram-approved jobs can be published")
            video_path = Path(job["video_path"])
            validate_render(video_path, Path(job["manifest_path"]))
            metadata_path = args.metadata or Path(job["manifest_path"]).with_name("social_metadata.json")
            caption = load_metadata(metadata_path)["caption"]
            platforms = ("facebook", "instagram") if args.platform == "both" else (args.platform,)
            ensure_publication_table(queue.connection)
            results: dict[str, str] = {}
            for platform in platforms:
                existing = queue.connection.execute(
                    "SELECT status, remote_id FROM meta_publications WHERE job_id=? AND platform=?",
                    (args.job_id, platform),
                ).fetchone()
                if existing and existing["status"] == "published":
                    results[platform] = existing["remote_id"]
                    continue
                record(queue.connection, args.job_id, platform, "publishing")
                try:
                    remote_id = (
                        publisher.publish_facebook(video_path, caption)
                        if platform == "facebook"
                        else publisher.publish_instagram(video_path, caption)
                    )
                    record(queue.connection, args.job_id, platform, "published", remote_id=remote_id)
                    results[platform] = remote_id
                except Exception as exc:
                    record(queue.connection, args.job_id, platform, "failed", error=str(exc)[:1000])
                    raise
            print(json.dumps({"job_id": args.job_id, "published": results}, indent=2))
            return 0
        finally:
            queue.close()
    except (MetaError, QueueError, requests.RequestException) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

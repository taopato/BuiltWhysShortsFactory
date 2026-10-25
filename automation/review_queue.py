from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT_DIR / "storage" / "approval_queue.sqlite3"
ALLOWED_TRANSITIONS = {
    "draft": {"rendering", "pending_review", "rejected"},
    "rendering": {"pending_review", "failed"},
    "pending_review": {"approved", "rejected", "revision_requested", "held"},
    "revision_requested": {"rendering", "rejected", "failed"},
    "held": {"pending_review", "rejected", "revision_requested"},
    "approved": {"publish_pending", "rejected", "revision_requested"},
    "publish_pending": {"published", "failed", "approved"},
    "failed": {"draft", "rendering", "pending_review", "revision_requested"},
    "rejected": {"draft"},
    "published": set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class VideoProbe:
    width: int
    height: int
    duration_seconds: float

    @property
    def is_vertical(self) -> bool:
        return self.height > self.width


class QueueError(RuntimeError):
    pass


class ApprovalQueue:
    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                script TEXT NOT NULL DEFAULT '',
                video_path TEXT NOT NULL DEFAULT '',
                manifest_path TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                decision_note TEXT NOT NULL DEFAULT '',
                telegram_message_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status);
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS weekly_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekday INTEGER NOT NULL CHECK(weekday BETWEEN 0 AND 6),
                local_time TEXT NOT NULL,
                platforms TEXT NOT NULL DEFAULT 'youtube,instagram,facebook',
                enabled INTEGER NOT NULL DEFAULT 1,
                UNIQUE(weekday, local_time)
            );
            """
        )
        columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(jobs)").fetchall()
        }
        if "review_action" not in columns:
            self.connection.execute(
                "ALTER TABLE jobs ADD COLUMN review_action TEXT NOT NULL DEFAULT ''"
            )
        self.connection.commit()

    def create_job(self, topic: str, title: str = "", script: str = "") -> dict[str, Any]:
        topic = topic.strip()
        if not topic:
            raise QueueError("topic cannot be empty")
        job_id = uuid.uuid4().hex[:12]
        now = utc_now()
        self.connection.execute(
            """
            INSERT INTO jobs(id, topic, title, script, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, topic, title.strip(), script.strip(), now, now),
        )
        self.connection.commit()
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise QueueError(f"job not found: {job_id}")
        return dict(row)

    def list_jobs(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.connection.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def attach_render(self, job_id: str, video_path: Path, manifest_path: Path) -> dict[str, Any]:
        video = Path(video_path).resolve()
        manifest = Path(manifest_path).resolve()
        validate_render(video, manifest)
        self._transition(
            job_id,
            "pending_review",
            video_path=str(video),
            manifest_path=str(manifest),
            decision_note="",
            review_action="",
        )
        return self.get_job(job_id)

    def start_render(self, job_id: str) -> dict[str, Any]:
        self._transition(job_id, "rendering")
        return self.get_job(job_id)

    def mark_failed(self, job_id: str, note: str) -> dict[str, Any]:
        self._transition(job_id, "failed", decision_note=note.strip())
        return self.get_job(job_id)

    def decide(self, job_id: str, decision: str, note: str = "") -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise QueueError("decision must be approved or rejected")
        self._transition(job_id, decision, decision_note=note.strip())
        return self.get_job(job_id)

    def request_revision(self, job_id: str, revision_type: str) -> dict[str, Any]:
        if revision_type not in {
            "visuals", "hybrid", "script", "topic", "hook", "voice", "subtitles", "metadata", "full"
        }:
            raise QueueError("unsupported revision type")
        self._transition(
            job_id,
            "revision_requested",
            review_action=revision_type,
            decision_note=f"Telegram revision request: {revision_type}",
        )
        return self.get_job(job_id)

    def hold(self, job_id: str) -> dict[str, Any]:
        self._transition(job_id, "held", review_action="hold", decision_note="Held in Telegram")
        return self.get_job(job_id)

    def get_bot_offset(self) -> int:
        row = self.connection.execute(
            "SELECT value FROM bot_state WHERE key = 'telegram_update_offset'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def set_bot_offset(self, offset: int) -> None:
        self.connection.execute(
            """
            INSERT INTO bot_state(key, value) VALUES ('telegram_update_offset', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (str(offset),),
        )
        self.connection.commit()

    def list_weekly_slots(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM weekly_slots WHERE enabled = 1 ORDER BY weekday, local_time"
        ).fetchall()
        return [dict(row) for row in rows]

    def add_weekly_slot(self, weekday: int, local_time: str) -> None:
        if weekday not in range(7) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", local_time):
            raise QueueError("invalid weekday or time")
        self.connection.execute(
            """
            INSERT INTO weekly_slots(weekday, local_time) VALUES (?, ?)
            ON CONFLICT(weekday, local_time) DO UPDATE SET enabled=1
            """,
            (weekday, local_time),
        )
        self.connection.commit()

    def remove_weekly_slot(self, weekday: int, local_time: str) -> None:
        self.connection.execute(
            "DELETE FROM weekly_slots WHERE weekday=? AND local_time=?",
            (weekday, local_time),
        )
        self.connection.commit()

    def clear_weekly_slots(self) -> None:
        self.connection.execute("DELETE FROM weekly_slots")
        self.connection.commit()

    def set_telegram_message(self, job_id: str, message_id: int) -> None:
        self.connection.execute(
            "UPDATE jobs SET telegram_message_id = ?, updated_at = ? WHERE id = ?",
            (message_id, utc_now(), job_id),
        )
        self.connection.commit()

    def _transition(self, job_id: str, target: str, **fields: Any) -> None:
        current = self.get_job(job_id)
        if target not in ALLOWED_TRANSITIONS.get(current["status"], set()):
            raise QueueError(f"invalid transition: {current['status']} -> {target}")
        assignments = ["status = ?", "updated_at = ?"]
        values: list[Any] = [target, utc_now()]
        for key, value in fields.items():
            if key not in {"video_path", "manifest_path", "decision_note", "review_action"}:
                raise QueueError(f"unsupported update field: {key}")
            assignments.append(f"{key} = ?")
            values.append(value)
        values.append(job_id)
        self.connection.execute(
            f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", values
        )
        self.connection.commit()


def probe_video(video_path: Path) -> VideoProbe:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise QueueError("ffprobe is required and was not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise QueueError(f"ffprobe rejected the video: {exc.stderr.strip()}") from exc
    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise QueueError("video has no readable video stream")
    duration = float((data.get("format") or {}).get("duration") or 0)
    return VideoProbe(
        width=int(streams[0].get("width") or 0),
        height=int(streams[0].get("height") or 0),
        duration_seconds=duration,
    )


def validate_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise QueueError(f"asset manifest does not exist: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QueueError(f"invalid asset manifest: {exc}") from exc
    assets = manifest.get("assets")
    sources = manifest.get("fact_sources")
    if not isinstance(assets, list) or not assets:
        raise QueueError("manifest must contain at least one asset")
    if not isinstance(sources, list) or len(sources) < 2:
        raise QueueError("manifest must contain at least two fact sources")
    for index, asset in enumerate(assets, start=1):
        required = {"type", "source_url", "license", "commercial_use"}
        missing = required.difference(asset if isinstance(asset, dict) else {})
        if missing:
            raise QueueError(f"asset {index} is missing: {', '.join(sorted(missing))}")
        if asset["commercial_use"] is not True:
            raise QueueError(f"asset {index} is not cleared for commercial use")
        if asset.get("type") == "ai_generated_image":
            if asset.get("generation_status") != "generated":
                raise QueueError(f"asset {index} has not been generated yet")
            source_url = str(asset.get("source_url", ""))
            if source_url.startswith("local://"):
                local_path = (ROOT_DIR / source_url.removeprefix("local://")).resolve()
                try:
                    local_path.relative_to(ROOT_DIR.resolve())
                except ValueError as exc:
                    raise QueueError(f"asset {index} escapes the project directory") from exc
                if not local_path.is_file():
                    raise QueueError(f"asset {index} file does not exist: {local_path}")
    return manifest


def validate_render(video_path: Path, manifest_path: Path) -> VideoProbe:
    if not video_path.is_file():
        raise QueueError(f"video does not exist: {video_path}")
    manifest = validate_manifest(manifest_path)
    probe = probe_video(video_path)
    if not probe.is_vertical:
        raise QueueError(f"video must be vertical, got {probe.width}x{probe.height}")
    if not 15 <= probe.duration_seconds <= 180:
        raise QueueError(
            f"video duration must be between 15 and 180 seconds, got {probe.duration_seconds:.1f}"
        )
    if manifest.get("ai_disclosure_required") not in {True, False}:
        raise QueueError("manifest must explicitly set ai_disclosure_required")
    return probe


def encode_multipart(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----ShortsApproval{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class TelegramApprovalBot:
    def __init__(self, queue: ApprovalQueue, token: str, chat_id: str) -> None:
        if not token or not chat_id:
            raise QueueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
        self.queue = queue
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.chat_id = str(chat_id)

    def _request(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = urllib.parse.urlencode(payload or {}).encode()
        request = urllib.request.Request(f"{self.base_url}/{method}", data=body)
        try:
            with urllib.request.urlopen(request, timeout=70) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise QueueError(f"Telegram request failed: {exc}") from exc
        if not result.get("ok"):
            raise QueueError(f"Telegram rejected {method}: {result}")
        return result["result"]

    def send_test_message(self) -> int:
        result = self._request(
            "sendMessage",
            {
                "chat_id": self.chat_id,
                "text": "✅ BuiltWhys approval bot is connected. Future candidate Shorts will arrive here for review.",
            },
        )
        return int(result["message_id"])

    def send_text(self, text: str) -> int:
        result = self._request(
            "sendMessage",
            {"chat_id": self.chat_id, "text": text, "disable_web_page_preview": "true"},
        )
        return int(result["message_id"])

    def send_for_review(self, job_id: str) -> int:
        job = self.queue.get_job(job_id)
        if job["status"] != "pending_review":
            raise QueueError("only pending_review jobs can be sent to Telegram")
        video_path = Path(job["video_path"])
        probe = validate_render(video_path, Path(job["manifest_path"]))
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Onayla", "callback_data": f"approve:{job_id}"},
                    {"text": "⏸ Beklet", "callback_data": f"hold:{job_id}"},
                ],
                [
                    {"text": "🎞 Görselleri Yenile", "callback_data": f"visuals:{job_id}"},
                    {"text": "📝 Metni Yenile", "callback_data": f"script:{job_id}"},
                ],
                [
                    {"text": "💡 Konuyu Değiştir", "callback_data": f"topic:{job_id}"},
                    {"text": "❌ Tamamen Reddet", "callback_data": f"reject:{job_id}"},
                ],
            ]
        }
        caption = (
            f"Review #{job_id}\n"
            f"{job['title'] or job['topic']}\n"
            f"{probe.width}x{probe.height} · {probe.duration_seconds:.1f}s\n\n"
            "Onay yalnızca yayın kuyruğuna alır; hemen paylaşmaz."
        )
        payload, content_type = encode_multipart(
            {
                "chat_id": self.chat_id,
                "caption": caption,
                "reply_markup": json.dumps(keyboard),
                "supports_streaming": "true",
                "width": str(probe.width),
                "height": str(probe.height),
                "duration": str(round(probe.duration_seconds)),
            },
            "video",
            video_path,
        )
        request = urllib.request.Request(
            f"{self.base_url}/sendVideo",
            data=payload,
            headers={"Content-Type": content_type},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise QueueError(f"Telegram video upload failed: {exc}") from exc
        if not result.get("ok"):
            raise QueueError(f"Telegram rejected video: {result}")
        message_id = int(result["result"]["message_id"])
        self.queue.set_telegram_message(job_id, message_id)
        return message_id

    def poll(self) -> None:
        offset = self.queue.get_bot_offset()
        consecutive_failures = 0
        print("Telegram approval bot is polling. Press Ctrl+C to stop.", flush=True)
        while True:
            try:
                updates = self._request("getUpdates", {"offset": offset, "timeout": 50})
                consecutive_failures = 0
            except QueueError as exc:
                consecutive_failures += 1
                retry_delay = min(30, max(2, consecutive_failures * 2))
                print(
                    f"Telegram polling warning: {exc}; retrying in {retry_delay}s",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(retry_delay)
                continue
            for update in updates:
                offset = max(offset, int(update["update_id"]) + 1)
                callback = update.get("callback_query")
                if callback:
                    try:
                        self._handle_callback(callback)
                    except QueueError as exc:
                        print(
                            f"Telegram callback warning: {exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                message = update.get("message")
                if message:
                    try:
                        self._handle_message(message)
                    except QueueError as exc:
                        print(
                            f"Telegram message warning: {exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                        try:
                            self.send_text(f"⚠️ {exc}")
                        except QueueError:
                            pass
                self.queue.set_bot_offset(offset)

    def sync_decision_message(self, job_id: str) -> None:
        job = self.queue.get_job(job_id)
        if job["status"] not in {"approved", "rejected", "revision_requested", "held"}:
            raise QueueError("only reviewed jobs can be synchronized")
        if not job["telegram_message_id"]:
            raise QueueError("job has no Telegram review message")
        self._request(
            "editMessageCaption",
            {
                "chat_id": self.chat_id,
                "message_id": job["telegram_message_id"],
                "caption": (
                    f"{job['title'] or job['topic']}\n\n"
                    f"Durum: {job['status'].upper()}"
                    + (f" ({job['review_action']})" if job.get("review_action") else "")
                    + "\nHenüz yayınlanmadı."
                ),
                "reply_markup": json.dumps({"inline_keyboard": []}),
            },
        )

    def _handle_callback(self, callback: dict[str, Any]) -> None:
        callback_id = callback.get("id", "")
        message = callback.get("message") or {}
        callback_chat = str((message.get("chat") or {}).get("id", ""))
        if callback_chat != self.chat_id:
            self._request(
                "answerCallbackQuery",
                {"callback_query_id": callback_id, "text": "Not authorized", "show_alert": "true"},
            )
            return
        action, separator, job_id = str(callback.get("data", "")).partition(":")
        if not separator or action not in {"approve", "reject", "hold", "visuals", "script", "topic"}:
            self._request("answerCallbackQuery", {"callback_query_id": callback_id, "text": "Unknown action"})
            return
        try:
            if action == "approve":
                decision = "approved"
                self.queue.decide(job_id, decision, "Telegram decision")
            elif action == "reject":
                decision = "rejected"
                self.queue.decide(job_id, decision, "Telegram decision")
            elif action == "hold":
                decision = "held"
                self.queue.hold(job_id)
            else:
                decision = f"revision: {action}"
                self.queue.request_revision(job_id, action)
            self.sync_decision_message(job_id)
            try:
                self._request(
                    "answerCallbackQuery",
                    {"callback_query_id": callback_id, "text": decision.replace("_", " ").title()},
                )
            except QueueError as exc:
                print(
                    f"Telegram callback acknowledgement warning: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
        except QueueError as exc:
            self._request(
                "answerCallbackQuery",
                {"callback_query_id": callback_id, "text": str(exc)[:180], "show_alert": "true"},
            )

    @staticmethod
    def _parse_weekday(value: str) -> int:
        aliases = {
            "mon": 0, "monday": 0, "pzt": 0, "pazartesi": 0,
            "tue": 1, "tuesday": 1, "sal": 1, "sali": 1, "salı": 1,
            "wed": 2, "wednesday": 2, "car": 2, "çar": 2,
            "carsamba": 2, "çarşamba": 2,
            "thu": 3, "thursday": 3, "per": 3,
            "persembe": 3, "perşembe": 3,
            "fri": 4, "friday": 4, "cum": 4, "cuma": 4,
            "sat": 5, "saturday": 5, "cmt": 5, "cumartesi": 5,
            "sun": 6, "sunday": 6, "paz": 6, "pazar": 6,
        }
        try:
            return aliases[value.strip().lower()]
        except KeyError as exc:
            raise QueueError("Gün anlaşılmadı. Örnek: /addslot sal 22:30") from exc

    def _plan_text(self) -> str:
        names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        slots = self.queue.list_weekly_slots()
        if not slots:
            return "📅 Haftalık plan boş.\nÖrnek: /addslot sal 22:30"
        lines = ["📅 BuiltWhys haftalık yayın planı (İstanbul):"]
        for slot in slots:
            lines.append(
                f"• {names[int(slot['weekday'])]} {slot['local_time']} — "
                "YouTube + Instagram + Facebook"
            )
        lines.append(f"\nHaftalık video sayısı: {len(slots)}")
        return "\n".join(lines)

    def _handle_message(self, message: dict[str, Any]) -> None:
        message_chat = str((message.get("chat") or {}).get("id", ""))
        if message_chat != self.chat_id:
            return
        text = str(message.get("text") or "").strip()
        if not text.startswith("/"):
            return
        parts = text.split()
        command = parts[0].split("@", 1)[0].lower()
        if command in {"/plan", "/schedule"}:
            self.send_text(self._plan_text())
        elif command == "/addslot":
            if len(parts) != 3:
                raise QueueError("Kullanım: /addslot sal 22:30")
            self.queue.add_weekly_slot(self._parse_weekday(parts[1]), parts[2])
            self.send_text("✅ Yayın saati eklendi.\n\n" + self._plan_text())
        elif command == "/removeslot":
            if len(parts) != 3:
                raise QueueError("Kullanım: /removeslot sal 22:30")
            self.queue.remove_weekly_slot(self._parse_weekday(parts[1]), parts[2])
            self.send_text("🗑 Yayın saati kaldırıldı.\n\n" + self._plan_text())
        elif command == "/clearplan":
            self.queue.clear_weekly_slots()
            self.send_text("🗑 Haftalık yayın planı temizlendi.")
        elif command in {"/help", "/start"}:
            self.send_text(
                "BuiltWhys komutları:\n"
                "/plan — haftalık planı göster\n"
                "/addslot sal 22:30 — üç platforma yayın saati ekle\n"
                "/removeslot sal 22:30 — saati kaldır\n"
                "/clearplan — planı temizle\n\n"
                "Haftalık video sayısı, eklediğin slot sayısıdır."
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Human approval queue for generated Shorts")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--topic", required=True)
    create.add_argument("--title", default="")
    create.add_argument("--script", default="")

    attach = subparsers.add_parser("attach")
    attach.add_argument("job_id")
    attach.add_argument("--video", type=Path, required=True)
    attach.add_argument("--manifest", type=Path, required=True)

    decide = subparsers.add_parser("decide")
    decide.add_argument("job_id")
    decide.add_argument("decision", choices=["approved", "rejected"])
    decide.add_argument("--note", default="")

    listing = subparsers.add_parser("list")
    listing.add_argument("--status", default=None)

    send = subparsers.add_parser("send")
    send.add_argument("job_id")

    sync = subparsers.add_parser("sync")
    sync.add_argument("job_id")

    subparsers.add_parser("ping")
    subparsers.add_parser("poll")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue = ApprovalQueue(args.db)
    try:
        if args.command == "create":
            result = queue.create_job(args.topic, args.title, args.script)
        elif args.command == "attach":
            result = queue.attach_render(args.job_id, args.video, args.manifest)
        elif args.command == "decide":
            result = queue.decide(args.job_id, args.decision, args.note)
        elif args.command == "list":
            result = queue.list_jobs(args.status)
        else:
            bot = TelegramApprovalBot(
                queue,
                os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                os.environ.get("TELEGRAM_CHAT_ID", ""),
            )
            if args.command == "send":
                result = {"message_id": bot.send_for_review(args.job_id)}
            elif args.command == "sync":
                bot.sync_decision_message(args.job_id)
                result = {"job_id": args.job_id, "synchronized": True}
            elif args.command == "ping":
                result = {"message_id": bot.send_test_message()}
            else:
                bot.poll()
                return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except QueueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        queue.close()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    from automation.review_queue import ApprovalQueue, DEFAULT_DB, QueueError, utc_now
    from automation.originality import assess_job
    from automation.production_quality import assess_production
except ImportError:
    from review_queue import ApprovalQueue, DEFAULT_DB, QueueError, utc_now
    from originality import assess_job
    from production_quality import assess_production


DEFAULT_SLOTS = (
    (0, "22:30"),  # Monday
    (2, "23:00"),  # Wednesday
    (4, "22:00"),  # Friday
    (6, "21:30"),  # Sunday
)
DEFAULT_PLATFORMS = "youtube,instagram,facebook"
APP_ROOT = Path(__file__).resolve().parents[1]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def local_timezone(name: str):
    """Return the configured zone, with a safe Istanbul fallback on bare Windows."""
    try:
        return ZoneInfo(name)
    except Exception:
        if name != "Europe/Istanbul":
            raise
        return timezone(timedelta(hours=3), name="Europe/Istanbul")


class ControlCenterStore:
    """Persistent control-plane state shared by the UI and every worker.

    SQLite/WAL is intentional for the first single-server deployment. Workers
    take short transactions and heavy render/publish work happens outside them.
    """

    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        self.queue = ApprovalQueue(db_path)
        self.connection = self.queue.connection
        self._migrate()

    def close(self) -> None:
        self.queue.close()

    def _migrate(self) -> None:
        columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(jobs)")
        }
        additions = {
            "description": "TEXT NOT NULL DEFAULT ''",
            "hashtags": "TEXT NOT NULL DEFAULT ''",
            "language": "TEXT NOT NULL DEFAULT 'en-US'",
            "platforms": f"TEXT NOT NULL DEFAULT '{DEFAULT_PLATFORMS}'",
            "quality_score": "INTEGER NOT NULL DEFAULT 50",
            "is_reserve": "INTEGER NOT NULL DEFAULT 0",
            "version": "INTEGER NOT NULL DEFAULT 1",
            "parent_job_id": "TEXT NOT NULL DEFAULT ''",
            "thumbnail_path": "TEXT NOT NULL DEFAULT ''",
            "metadata_path": "TEXT NOT NULL DEFAULT ''",
            "pilot_dir": "TEXT NOT NULL DEFAULT ''",
            "published_at": "TEXT NOT NULL DEFAULT ''",
            "originality_score": "INTEGER NOT NULL DEFAULT 0",
            "policy_status": "TEXT NOT NULL DEFAULT 'not_checked'",
            "policy_report": "TEXT NOT NULL DEFAULT '{}'",
            "human_reviewed": "INTEGER NOT NULL DEFAULT 0",
            "human_reviewed_at": "TEXT NOT NULL DEFAULT ''",
            "human_review_note": "TEXT NOT NULL DEFAULT ''",
            "youtube_privacy": "TEXT NOT NULL DEFAULT 'private'",
            "technical_score": "INTEGER NOT NULL DEFAULT 0",
            "quality_status": "TEXT NOT NULL DEFAULT 'not_checked'",
            "quality_report": "TEXT NOT NULL DEFAULT '{}'",
            "story_id": "TEXT NOT NULL DEFAULT ''",
            "source_job_id": "TEXT NOT NULL DEFAULT ''",
            "channel_key": "TEXT NOT NULL DEFAULT 'builtwhys'",
            "candidate_score": "INTEGER NOT NULL DEFAULT 0",
            "candidate_report": "TEXT NOT NULL DEFAULT '{}'",
            "revision_note": "TEXT NOT NULL DEFAULT ''",
        }
        for name, definition in additions.items():
            if name not in columns:
                self.connection.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")

        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schedule_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scheduled_at TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Europe/Istanbul',
                job_id TEXT NOT NULL DEFAULT '',
                platforms TEXT NOT NULL DEFAULT 'youtube,instagram,facebook',
                source TEXT NOT NULL DEFAULT 'manual',
                status TEXT NOT NULL DEFAULT 'planned',
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(scheduled_at)
            );
            CREATE INDEX IF NOT EXISTS schedule_due_idx
                ON schedule_entries(status, scheduled_at);

            CREATE TABLE IF NOT EXISTS publications (
                job_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                remote_id TEXT NOT NULL DEFAULT '',
                remote_url TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                attempts INTEGER NOT NULL DEFAULT 0,
                published_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(job_id, platform)
            );

            CREATE TABLE IF NOT EXISTS analytics_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                views INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                saves INTEGER NOT NULL DEFAULT 0,
                watch_seconds REAL NOT NULL DEFAULT 0,
                average_view_percentage REAL NOT NULL DEFAULT 0,
                followers_gained INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS analytics_job_idx
                ON analytics_snapshots(job_id, platform, captured_at DESC);

            CREATE TABLE IF NOT EXISTS channel_analytics_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                views INTEGER NOT NULL DEFAULT 0,
                followers INTEGER NOT NULL DEFAULT 0,
                media_count INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS channel_analytics_platform_idx
                ON channel_analytics_snapshots(platform, captured_at DESC);

            CREATE TABLE IF NOT EXISTS geo_analytics_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                period_days INTEGER NOT NULL DEFAULT 90,
                country TEXT NOT NULL,
                views INTEGER NOT NULL DEFAULT 0,
                watch_seconds REAL NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS geo_analytics_platform_idx
                ON geo_analytics_snapshots(platform, captured_at DESC, views DESC);

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                job_id TEXT NOT NULL DEFAULT '',
                details_json TEXT NOT NULL DEFAULT '{}',
                acknowledged INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_created_idx ON events(created_at DESC);

            CREATE TABLE IF NOT EXISTS service_heartbeats (
                service TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        if not self.connection.execute("SELECT 1 FROM weekly_slots LIMIT 1").fetchone():
            self.connection.executemany(
                "INSERT INTO weekly_slots(weekday, local_time, platforms, enabled) VALUES (?,?,?,1)",
                [(weekday, local_time, DEFAULT_PLATFORMS) for weekday, local_time in DEFAULT_SLOTS],
            )
        defaults = {
            "timezone": "Europe/Istanbul",
            "reserve_minimum": "6",
            "reserve_target": "8",
            "schedule_horizon_days": "21",
            "auto_fill_schedule": "true",
            "allow_unapproved_fallback": "false",
            "publishing_enabled": "false",
            "telegram_notifications": "true",
            "max_publications_per_day": "1",
            "localization_languages": "tr-TR",
            "auto_localize_approved": "false",
        }
        for key, value in defaults.items():
            self.connection.execute(
                "INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES (?,?,?)",
                (key, value, utc_now()),
            )
        # Preserve the manually uploaded first Short and never upload it to
        # YouTube a second time. Other legacy approvals become reserve items.
        self.connection.execute(
            """INSERT OR IGNORE INTO publications(
               job_id,platform,status,remote_id,remote_url,published_at,updated_at)
               SELECT id,'youtube','published','','',updated_at,updated_at FROM jobs
               WHERE status='approved' AND decision_note LIKE '%YouTube upload%'"""
        )
        self.connection.execute(
            """UPDATE jobs SET is_reserve=1 WHERE status='approved' AND is_reserve=0
               AND decision_note NOT LIKE '%YouTube upload%'
               AND NOT EXISTS (SELECT 1 FROM schedule_entries s WHERE s.job_id=jobs.id
                   AND s.status IN ('planned','publishing'))"""
        )
        self.connection.execute(
            """UPDATE jobs SET is_reserve=0 WHERE EXISTS (
               SELECT 1 FROM schedule_entries s WHERE s.job_id=jobs.id
               AND s.status IN ('planned','publishing'))"""
        )
        self.connection.execute(
            """UPDATE jobs SET pilot_dir=CASE
               WHEN manifest_path<>'' THEN replace(manifest_path, '\\manifest-v3.json','')
               ELSE pilot_dir END
               WHERE pilot_dir='' AND manifest_path LIKE '%manifest-v3.json'"""
        )
        self.connection.execute("UPDATE jobs SET story_id=id WHERE story_id='' OR story_id IS NULL")
        self._remap_local_paths()
        self.connection.commit()

    def _remap_local_paths(self) -> None:
        """Make Windows-created queue records portable to the Linux container."""
        fields = ("video_path", "manifest_path", "thumbnail_path", "metadata_path", "pilot_dir")
        rows = self.connection.execute(
            "SELECT id," + ",".join(fields) + " FROM jobs"
        ).fetchall()
        for row in rows:
            updates: dict[str, str] = {}
            for field in fields:
                value = str(row[field] or "")
                if not value or Path(value).exists():
                    continue
                normalized = value.replace("\\", "/")
                for marker in ("/storage/", "/automation/"):
                    index = normalized.lower().find(marker)
                    if index >= 0:
                        candidate = APP_ROOT / normalized[index + 1:]
                        if candidate.exists():
                            updates[field] = str(candidate.resolve())
                        break
            if updates:
                assignments = ",".join(f"{name}=?" for name in updates)
                self.connection.execute(
                    f"UPDATE jobs SET {assignments} WHERE id=?",
                    [*updates.values(), row["id"]],
                )

    def setting(self, key: str, default: str = "") -> str:
        row = self.connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def settings(self) -> dict[str, str]:
        return {row["key"]: row["value"] for row in self.connection.execute("SELECT * FROM settings")}

    def set_setting(self, key: str, value: str) -> None:
        self.connection.execute(
            """INSERT INTO settings(key,value,updated_at) VALUES (?,?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, utc_now()),
        )
        self.connection.commit()

    def event(self, level: str, kind: str, message: str, job_id: str = "", **details: Any) -> None:
        self.connection.execute(
            "INSERT INTO events(level,kind,message,job_id,details_json,created_at) VALUES (?,?,?,?,?,?)",
            (level, kind, message, job_id, _json(details), utc_now()),
        )
        self.connection.commit()

    def heartbeat(self, service: str, status: str = "ok", detail: str = "") -> None:
        self.connection.execute(
            """INSERT INTO service_heartbeats(service,status,detail,updated_at) VALUES (?,?,?,?)
               ON CONFLICT(service) DO UPDATE SET status=excluded.status,
               detail=excluded.detail, updated_at=excluded.updated_at""",
            (service, status, detail[:1000], utc_now()),
        )
        self.connection.commit()

    def update_job(self, job_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "title", "topic", "script", "description", "hashtags", "language",
            "platforms", "quality_score", "is_reserve", "thumbnail_path",
            "metadata_path", "pilot_dir", "decision_note", "youtube_privacy",
            "story_id", "source_job_id", "channel_key", "candidate_score", "candidate_report",
            "revision_note",
        }
        clean = {key: value for key, value in fields.items() if key in allowed}
        if not clean:
            return self.job(job_id)
        if "quality_score" in clean:
            clean["quality_score"] = max(0, min(100, int(clean["quality_score"])))
        if "candidate_score" in clean:
            clean["candidate_score"] = max(0, min(100, int(clean["candidate_score"])))
        if "is_reserve" in clean:
            clean["is_reserve"] = int(bool(clean["is_reserve"]))
        if "youtube_privacy" in clean and clean["youtube_privacy"] not in {"private", "unlisted", "public"}:
            raise QueueError("youtube_privacy must be private, unlisted or public")
        before = self.queue.get_job(job_id)
        assignments = [f"{key}=?" for key in clean] + ["updated_at=?"]
        values = list(clean.values()) + [utc_now(), job_id]
        cursor = self.connection.execute(
            f"UPDATE jobs SET {', '.join(assignments)} WHERE id=?", values
        )
        if cursor.rowcount != 1:
            raise QueueError(f"job not found: {job_id}")
        if {"title", "topic", "script"} & set(clean):
            self.connection.execute(
                """UPDATE jobs SET policy_status='not_checked',policy_report='{}',originality_score=0,
                   quality_status='not_checked',quality_report='{}',technical_score=0,
                   human_reviewed=0,human_reviewed_at='',human_review_note='',
                   status=CASE WHEN status='approved' THEN 'pending_review' ELSE status END,
                   is_reserve=CASE WHEN status='approved' THEN 0 ELSE is_reserve END WHERE id=?""",
                (job_id,),
            )
            if before["status"] == "approved":
                self.connection.execute(
                    "UPDATE schedule_entries SET job_id='',source='default',updated_at=? WHERE job_id=? AND status='planned'",
                    (utc_now(), job_id),
                )
        self.connection.commit()
        return self.job(job_id)

    def refresh_policy(self, job_id: str) -> dict[str, Any]:
        job = self.queue.get_job(job_id)
        report = assess_job(self.connection, job)
        self.connection.execute(
            "UPDATE jobs SET originality_score=?,policy_status=?,policy_report=?,updated_at=? WHERE id=?",
            (report["score"], report["status"], _json(report), utc_now(), job_id),
        )
        was_published = self.connection.execute(
            "SELECT 1 FROM publications WHERE job_id=? AND status='published' LIMIT 1", (job_id,),
        ).fetchone()
        if report["status"] != "pass" and job["status"] == "approved" and not was_published:
            self.connection.execute(
                """UPDATE jobs SET status='pending_review',is_reserve=0,human_reviewed=0,
                   human_reviewed_at='',human_review_note='',updated_at=? WHERE id=?""",
                (utc_now(), job_id),
            )
            self.connection.execute(
                "UPDATE schedule_entries SET job_id='',source='default',updated_at=? WHERE job_id=? AND status='planned'",
                (utc_now(), job_id),
            )
        self.connection.commit()
        return report

    def refresh_quality(self, job_id: str) -> dict[str, Any]:
        job = self.queue.get_job(job_id)
        report = assess_production(job)
        self.connection.execute(
            "UPDATE jobs SET technical_score=?,quality_status=?,quality_report=?,quality_score=?,updated_at=? WHERE id=?",
            (report["score"], report["status"], _json(report), report["score"], utc_now(), job_id),
        )
        self.connection.commit()
        return report

    def approve(self, job_id: str, note: str = "Control Center approval",
                human_confirmed: bool = False) -> dict[str, Any]:
        job = self.queue.get_job(job_id)
        report = self.refresh_policy(job_id)
        quality = self.refresh_quality(job_id)
        if report["status"] != "pass":
            raise QueueError("originality/policy gate blocked approval: " + "; ".join(report["blockers"][:3]))
        if quality["status"] != "pass":
            raise QueueError("production quality gate blocked approval: " + "; ".join(quality["blockers"][:3]))
        if not human_confirmed:
            raise QueueError("watch the complete video and confirm human review before approval")
        if job["status"] == "held":
            self.queue._transition(job_id, "pending_review")
        self.queue.decide(job_id, "approved", note)
        self.connection.execute(
            """UPDATE jobs SET is_reserve=1,human_reviewed=1,human_reviewed_at=?,
               human_review_note=?,updated_at=? WHERE id=?""",
            (utc_now(), note, utc_now(), job_id),
        )
        self.connection.commit()
        self.event("info", "approved", "Video approved and added to reserve", job_id)
        return self.job(job_id)

    def reject(self, job_id: str, note: str) -> dict[str, Any]:
        # The operator rejects the content, not only one technical version.
        # Leaving a parent or child revision alive causes the producer to show
        # the same topic again after it was explicitly cancelled.
        return self.reject_family(job_id, note or "Video rejected")

    def request_revision(self, job_id: str, revision_type: str, note: str = "") -> dict[str, Any]:
        original = self.queue.get_job(job_id)
        if original["status"] not in {"pending_review", "held", "approved", "failed"}:
            raise QueueError(f"cannot revise from {original['status']}")
        created = self.queue.create_job(original["topic"], original["title"], original["script"])
        new_id = created["id"]
        copy_fields = {
            "description": original.get("description", ""),
            "hashtags": original.get("hashtags", ""),
            "language": original.get("language", "en-US"),
            "platforms": original.get("platforms", DEFAULT_PLATFORMS),
            "quality_score": original.get("quality_score", 50),
            "metadata_path": original.get("metadata_path", ""),
            "pilot_dir": original.get("pilot_dir", "") or str(Path(original.get("manifest_path", "")).parent),
            "channel_key": original.get("channel_key", "builtwhys"),
            "candidate_score": original.get("candidate_score", 0),
            "candidate_report": original.get("candidate_report", "{}"),
            "revision_note": note.strip(),
        }
        self.update_job(new_id, copy_fields)
        self.connection.execute(
            """UPDATE jobs SET status='revision_requested',review_action=?,parent_job_id=?,version=?,
               manifest_path=?,decision_note=?,story_id=?,source_job_id=?,updated_at=? WHERE id=?""",
            (revision_type, job_id, int(original.get("version", 1)) + 1,
             original.get("manifest_path", ""), note or f"Control Center revision: {revision_type}",
             original.get("story_id") or original["id"], original.get("source_job_id", ""),
             utc_now(), new_id),
        )
        self.connection.execute(
            "UPDATE jobs SET status='held',is_reserve=0,decision_note=?,updated_at=? WHERE id=?",
            (f"Superseded by revision {new_id}", utc_now(), job_id),
        )
        self.connection.execute(
            "UPDATE schedule_entries SET job_id='',source='default',updated_at=? WHERE job_id=? AND status='planned'",
            (utc_now(), job_id),
        )
        self.connection.commit()
        self.event(
            "info", "revision_requested",
            f"Revision V{int(original.get('version', 1)) + 1}: {revision_type}",
            new_id, parent_job_id=job_id, revision_note=note.strip(),
        )
        return self.job(new_id)

    def create_localization(self, job_id: str, language: str) -> dict[str, Any]:
        if language not in {"tr-TR"}:
            raise QueueError("unsupported localization language")
        source = self.queue.get_job(job_id)
        story_id = str(source.get("story_id") or source["id"])
        existing = self.connection.execute(
            """SELECT id FROM jobs WHERE story_id=? AND language=?
               AND status NOT IN ('rejected','failed') ORDER BY created_at DESC LIMIT 1""",
            (story_id, language),
        ).fetchone()
        if existing:
            return self.job(str(existing["id"]))
        created = self.queue.create_job(source["topic"], source["title"], source["script"])
        new_id = created["id"]
        self.update_job(new_id, {
            "language": language, "platforms": source.get("platforms", DEFAULT_PLATFORMS),
            "pilot_dir": source.get("pilot_dir", "") or str(Path(source.get("manifest_path", "")).parent),
            "story_id": story_id, "source_job_id": source["id"],
            "channel_key": source.get("channel_key", "builtwhys"),
            "candidate_score": source.get("candidate_score", 0),
            "candidate_report": source.get("candidate_report", "{}"),
        })
        self.connection.execute(
            """UPDATE jobs SET status='revision_requested',review_action='localize',
               manifest_path=?,decision_note=?,updated_at=? WHERE id=?""",
            (source.get("manifest_path", ""), f"Localization from {source['id']} to {language}", utc_now(), new_id),
        )
        self.connection.commit()
        self.event("info", "localization_requested", f"{language} localization queued", new_id,
                   source_job_id=source["id"], story_id=story_id)
        return self.job(new_id)

    def reject_family(self, job_id: str, note: str) -> dict[str, Any]:
        selected = self.queue.get_job(job_id)
        story_id = str(selected.get("story_id") or selected["id"])
        family_ids = {job_id, story_id}
        parent = str(selected.get("parent_job_id") or "")
        while parent and parent not in family_ids:
            family_ids.add(parent)
            row = self.connection.execute(
                "SELECT parent_job_id FROM jobs WHERE id=?", (parent,),
            ).fetchone()
            parent = str(row["parent_job_id"] or "") if row else ""
        # Include legacy roots with an empty story_id and every descendant,
        # even when a revision was created before story tracking was added.
        changed = True
        while changed:
            changed = False
            placeholders = ",".join("?" for _ in family_ids)
            rows = self.connection.execute(
                f"""SELECT id FROM jobs WHERE story_id=? OR id IN ({placeholders})
                    OR parent_job_id IN ({placeholders}) OR source_job_id IN ({placeholders})""",
                (story_id, *family_ids, *family_ids, *family_ids),
            ).fetchall()
            for row in rows:
                if str(row["id"]) not in family_ids:
                    family_ids.add(str(row["id"]))
                    changed = True
        placeholders = ",".join("?" for _ in family_ids)
        rows = self.connection.execute(
            f"SELECT id,status FROM jobs WHERE id IN ({placeholders}) AND status NOT IN ('published','rejected')",
            tuple(family_ids),
        ).fetchall()
        for row in rows:
            if row["status"] in {"pending_review", "held", "approved", "revision_requested", "draft", "rendering", "failed"}:
                self.connection.execute(
                    """UPDATE jobs SET status='rejected',is_reserve=0,decision_note=?,review_action='',updated_at=?
                       WHERE id=?""", (note, utc_now(), row["id"]),
                )
                self.connection.execute(
                    "UPDATE schedule_entries SET status='cancelled',note=?,updated_at=? WHERE job_id=? AND status='planned'",
                    (note, utc_now(), row["id"]),
                )
        self.connection.commit()
        self.event("info", "family_rejected", note, job_id, story_id=story_id,
                   rejected_versions=len(rows))
        return self.job(job_id)

    def job(self, job_id: str) -> dict[str, Any]:
        job = self.queue.get_job(job_id)
        try:
            job["policy_report"] = json.loads(job.get("policy_report") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            job["policy_report"] = {}
        try:
            job["quality_report"] = json.loads(job.get("quality_report") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            job["quality_report"] = {}
        story_id = str(job.get("story_id") or job["id"])
        job["family"] = [dict(row) for row in self.connection.execute(
            """SELECT id,language,title,status,version,parent_job_id,review_action,revision_note,
                      originality_score,technical_score,human_reviewed
               FROM jobs WHERE story_id=? ORDER BY language,created_at DESC""", (story_id,),
        )]
        job["publications"] = [
            dict(row) for row in self.connection.execute(
                "SELECT * FROM publications WHERE job_id=? ORDER BY platform", (job_id,)
            )
        ]
        job["analytics"] = [
            dict(row) for row in self.connection.execute(
                """SELECT a.* FROM analytics_snapshots a
                   JOIN (SELECT platform, MAX(captured_at) captured_at FROM analytics_snapshots
                         WHERE job_id=? GROUP BY platform) latest
                   ON latest.platform=a.platform AND latest.captured_at=a.captured_at
                   WHERE a.job_id=?""", (job_id, job_id)
            )
        ]
        job["schedule"] = [
            dict(row) for row in self.connection.execute(
                "SELECT * FROM schedule_entries WHERE job_id=? ORDER BY scheduled_at", (job_id,)
            )
        ]
        job["planned_platforms"] = [
            str(item["platforms"]) for item in job["schedule"] if item.get("status") == "planned"
        ]
        return job

    def jobs(self, status: str = "", query: str = "", language: str = "",
             channel_key: str = "", view_filter: str = "") -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if view_filter == "pending":
            # Superseded parents are implementation history, not work waiting
            # for the owner's decision. Showing held versions here made one
            # revision family look like several independently active videos.
            clauses.append("status='pending_review'")
        elif view_filter == "pool":
            clauses.append("status='approved'")
        elif view_filter == "rejected":
            clauses.append("status IN ('rejected','failed')")
        elif view_filter == "published":
            clauses.append("(status='published' OR EXISTS (SELECT 1 FROM publications p WHERE p.job_id=jobs.id AND p.status='published'))")
        elif status:
            clauses.append("status=?")
            values.append(status)
        if query:
            clauses.append("(topic LIKE ? OR title LIKE ? OR script LIKE ?)")
            term = f"%{query}%"
            values.extend((term, term, term))
        if language:
            clauses.append("language=?")
            values.append(language)
        if channel_key:
            clauses.append("channel_key=?")
            values.append(channel_key)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.connection.execute(
            f"SELECT * FROM jobs{where} ORDER BY is_reserve DESC, quality_score DESC, created_at DESC",
            values,
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            latest = self.connection.execute(
                "SELECT SUM(views) views,SUM(likes) likes,SUM(comments) comments FROM ("
                "SELECT a.* FROM analytics_snapshots a JOIN (SELECT platform,MAX(captured_at) c "
                "FROM analytics_snapshots WHERE job_id=? GROUP BY platform) x "
                "ON a.platform=x.platform AND a.captured_at=x.c WHERE a.job_id=?)",
                (item["id"], item["id"]),
            ).fetchone()
            item["metrics"] = dict(latest) if latest else {"views": 0, "likes": 0, "comments": 0}
            item["publications"] = [dict(publication) for publication in self.connection.execute(
                "SELECT platform,status,remote_url,error FROM publications WHERE job_id=? ORDER BY platform",
                (item["id"],),
            )]
            item["planned_platforms"] = [str(schedule["platforms"]) for schedule in self.connection.execute(
                "SELECT platforms FROM schedule_entries WHERE job_id=? AND status='planned' ORDER BY scheduled_at",
                (item["id"],),
            )]
            result.append(item)
        return result

    def schedule(self, job_id: str, scheduled_at: str, platforms: str = DEFAULT_PLATFORMS,
                 source: str = "manual") -> dict[str, Any]:
        job = self.queue.get_job(job_id)
        if job["status"] != "approved":
            raise QueueError("only approved videos can be scheduled")
        report = self.refresh_policy(job_id)
        job = self.queue.get_job(job_id)
        if report["status"] != "pass" or not job.get("human_reviewed"):
            raise QueueError("video must pass the originality gate and human review before scheduling")
        try:
            parsed = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise QueueError("invalid scheduled_at") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=local_timezone(self.setting("timezone", "Europe/Istanbul")))
        local_tz = local_timezone(self.setting("timezone", "Europe/Istanbul"))
        local_day = parsed.astimezone(local_tz).date()
        day_start = datetime(local_day.year, local_day.month, local_day.day, tzinfo=local_tz)
        day_end = day_start + timedelta(days=1)
        daily_count = self.connection.execute(
            """SELECT COUNT(*) count FROM schedule_entries WHERE job_id<>'' AND status IN ('planned','publishing')
               AND scheduled_at>=? AND scheduled_at<? AND scheduled_at<>?""",
            (day_start.astimezone(timezone.utc).isoformat(timespec="seconds"),
             day_end.astimezone(timezone.utc).isoformat(timespec="seconds"),
             parsed.astimezone(timezone.utc).isoformat(timespec="seconds")),
        ).fetchone()["count"]
        if daily_count >= int(self.setting("max_publications_per_day", "1")):
            raise QueueError("daily publication limit reached; choose another day")
        canonical = parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
        now = utc_now()
        self.connection.execute(
            """INSERT INTO schedule_entries(scheduled_at,timezone,job_id,platforms,source,status,created_at,updated_at)
               VALUES (?,?,?,?,?,'planned',?,?)
               ON CONFLICT(scheduled_at) DO UPDATE SET job_id=excluded.job_id,
               platforms=excluded.platforms,source=excluded.source,status='planned',updated_at=excluded.updated_at""",
            (canonical, self.setting("timezone", "Europe/Istanbul"), job_id, platforms, source, now, now),
        )
        self.update_job(job_id, {"is_reserve": False, "platforms": platforms})
        self.connection.commit()
        self.event("info", "scheduled", f"Video scheduled for {canonical}", job_id)
        return self.schedule_entry(canonical)

    def unschedule(self, schedule_id: int) -> None:
        row = self.connection.execute("SELECT * FROM schedule_entries WHERE id=?", (schedule_id,)).fetchone()
        if not row:
            raise QueueError("schedule entry not found")
        self.connection.execute("DELETE FROM schedule_entries WHERE id=?", (schedule_id,))
        if row["job_id"]:
            self.update_job(row["job_id"], {"is_reserve": True})
        self.connection.commit()

    def schedule_entry(self, scheduled_at: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM schedule_entries WHERE scheduled_at=?", (scheduled_at,)
        ).fetchone()
        if not row:
            raise QueueError("schedule entry not found")
        return dict(row)

    def schedules(self, start: str = "", end: str = "") -> list[dict[str, Any]]:
        clauses, values = [], []
        if start:
            clauses.append("scheduled_at>=?")
            values.append(start)
        if end:
            clauses.append("scheduled_at<=?")
            values.append(end)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.connection.execute(
            "SELECT s.*,j.title,j.topic,j.status job_status,j.video_path FROM schedule_entries s "
            "LEFT JOIN jobs j ON j.id=s.job_id" + where + " ORDER BY scheduled_at", values
        ).fetchall()
        return [dict(row) for row in rows]

    def ensure_schedule_horizon(self, now: datetime | None = None) -> int:
        tz_name = self.setting("timezone", "Europe/Istanbul")
        tz = local_timezone(tz_name)
        local_now = (now or datetime.now(timezone.utc)).astimezone(tz)
        horizon = int(self.setting("schedule_horizon_days", "21"))
        slots = self.queue.list_weekly_slots()
        created = 0
        for offset in range(horizon + 1):
            day = (local_now + timedelta(days=offset)).date()
            for slot in slots:
                if day.weekday() != int(slot["weekday"]):
                    continue
                hour, minute = map(int, slot["local_time"].split(":"))
                local_dt = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
                if local_dt <= local_now:
                    continue
                scheduled_at = local_dt.astimezone(timezone.utc).isoformat(timespec="seconds")
                cursor = self.connection.execute(
                    """INSERT OR IGNORE INTO schedule_entries(
                       scheduled_at,timezone,platforms,source,status,created_at,updated_at)
                       VALUES (?,?,?,'default','planned',?,?)""",
                    (scheduled_at, tz_name, slot["platforms"], utc_now(), utc_now()),
                )
                created += cursor.rowcount
        self.connection.commit()
        return created

    def auto_assign(self) -> int:
        assigned = 0
        entries = self.connection.execute(
            "SELECT * FROM schedule_entries WHERE status='planned' AND job_id='' ORDER BY scheduled_at"
        ).fetchall()
        used = {
            row["job_id"] for row in self.connection.execute(
                "SELECT job_id FROM schedule_entries WHERE status IN ('planned','publishing') AND job_id<>''"
            )
        }
        for entry in entries:
            placeholders = ",".join("?" for _ in used) or "''"
            params: list[Any] = list(used)
            candidate = self.connection.execute(
                f"""SELECT * FROM jobs WHERE status='approved' AND is_reserve=1
                    AND policy_status='pass' AND human_reviewed=1
                    AND id NOT IN ({placeholders})
                    ORDER BY technical_score DESC, originality_score DESC,
                             candidate_score DESC, quality_score DESC, created_at ASC LIMIT 1""", params
            ).fetchone()
            if not candidate:
                break
            self.connection.execute(
                "UPDATE schedule_entries SET job_id=?,source='auto',updated_at=? WHERE id=?",
                (candidate["id"], utc_now(), entry["id"]),
            )
            self.connection.execute(
                "UPDATE jobs SET is_reserve=0,platforms=?,updated_at=? WHERE id=?",
                (entry["platforms"], utc_now(), candidate["id"]),
            )
            used.add(candidate["id"])
            assigned += 1
        self.connection.commit()
        return assigned

    def dashboard(self) -> dict[str, Any]:
        counts = {
            row["status"]: row["count"] for row in self.connection.execute(
                "SELECT status,COUNT(*) count FROM jobs GROUP BY status"
            )
        }
        reserve = self.connection.execute(
            "SELECT COUNT(*) count FROM jobs WHERE status='approved' AND is_reserve=1"
        ).fetchone()["count"]
        next_entry = self.connection.execute(
            """SELECT s.*,j.title,j.topic FROM schedule_entries s LEFT JOIN jobs j ON j.id=s.job_id
               WHERE s.status='planned' ORDER BY s.scheduled_at LIMIT 1"""
        ).fetchone()
        latest_metrics = self.connection.execute(
            """SELECT COALESCE(SUM(views),0) views,COALESCE(SUM(likes),0) likes,
               COALESCE(SUM(comments),0) comments FROM analytics_snapshots a
               WHERE captured_at IN (SELECT MAX(captured_at) FROM analytics_snapshots
               GROUP BY job_id,platform)"""
        ).fetchone()
        return {
            "counts": counts,
            "reserve": reserve,
            "reserve_minimum": int(self.setting("reserve_minimum", "6")),
            "next_schedule": dict(next_entry) if next_entry else None,
            "metrics": dict(latest_metrics),
            "services": [dict(row) for row in self.connection.execute(
                "SELECT * FROM service_heartbeats ORDER BY service"
            )],
            "settings": self.settings(),
        }

    def record_publication(self, job_id: str, platform: str, status: str,
                           remote_id: str = "", remote_url: str = "", error: str = "") -> None:
        now = utc_now()
        published_at = now if status == "published" else ""
        self.connection.execute(
            """INSERT INTO publications(job_id,platform,status,remote_id,remote_url,error,attempts,published_at,updated_at)
               VALUES (?,?,?,?,?,?,1,?,?) ON CONFLICT(job_id,platform) DO UPDATE SET
               status=excluded.status,remote_id=excluded.remote_id,remote_url=excluded.remote_url,
               error=excluded.error,attempts=publications.attempts+1,
               published_at=CASE WHEN excluded.status='published' THEN excluded.published_at ELSE publications.published_at END,
               updated_at=excluded.updated_at""",
            (job_id, platform, status, remote_id, remote_url, error[:2000], published_at, now),
        )
        self.connection.commit()


__all__ = ["ControlCenterStore", "DEFAULT_SLOTS", "DEFAULT_PLATFORMS"]

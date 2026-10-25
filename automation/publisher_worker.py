from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from control_center_store import ControlCenterStore
from meta_publish import MetaPublisher
from notifier import notify
from review_queue import DEFAULT_DB, QueueError, validate_render, utc_now
from youtube_publish import publish as publish_youtube


def caption(job: dict) -> str:
    description = str(job.get("description") or "").strip()
    if not description:
        description = str(job.get("script") or "").strip()
    hashtags = str(job.get("hashtags") or "").strip()
    return (description + ("\n\n" + hashtags if hashtags else ""))[:5000]


def publish_job(store: ControlCenterStore, job_id: str, platforms: str = "") -> bool:
    job = store.job(job_id)
    if job["status"] not in {"approved", "publish_pending", "failed"}:
        raise QueueError(f"job is not publishable from {job['status']}")
    if store.setting("publishing_enabled", "false") != "true" or os.environ.get("PUBLISH_ENABLED", "false").lower() != "true":
        store.event("warning", "publishing_disabled", "Publish time reached but live publishing is disabled", job_id)
        return False
    report = store.refresh_policy(job_id)
    quality = store.refresh_quality(job_id)
    job = store.job(job_id)
    if report["status"] != "pass" or quality["status"] != "pass" or not job.get("human_reviewed"):
        raise QueueError("publication blocked: originality, production quality or human review is incomplete")
    if job["status"] == "failed":
        store.queue._transition(job_id, "pending_review")
        store.queue.decide(job_id, "approved", "Automatic publication retry")
    if store.queue.get_job(job_id)["status"] == "approved":
        store.queue._transition(job_id, "publish_pending")
    video = Path(job["video_path"])
    validate_render(video, Path(job["manifest_path"]))
    selected = [p.strip() for p in (platforms or job.get("platforms") or "").split(",") if p.strip()]
    existing = {item["platform"]: item for item in job["publications"]}
    failures: list[str] = []
    text = caption(job)
    language = str(job.get("language") or "en-US")
    meta: MetaPublisher | None = None
    for platform in selected:
        if existing.get(platform, {}).get("status") == "published":
            continue
        store.record_publication(job_id, platform, "publishing")
        try:
            if platform == "youtube":
                remote_id, remote_url = publish_youtube(
                    video, job["title"] or job["topic"], text, job.get("hashtags", ""),
                    Path(job["thumbnail_path"]) if job.get("thumbnail_path") else None,
                    job.get("youtube_privacy", "private"),
                    language,
                )
            elif platform in {"facebook", "instagram"}:
                meta = meta or MetaPublisher(language)
                meta_text = text[:2100]
                remote_id = meta.publish_facebook(video, meta_text) if platform == "facebook" else meta.publish_instagram(video, meta_text)
                remote_url = ""
            else:
                raise QueueError(f"unsupported platform: {platform}")
            store.record_publication(job_id, platform, "published", remote_id, remote_url)
            store.event("info", "platform_published", f"Published to {platform}", job_id, remote_id=remote_id)
        except Exception as exc:
            failures.append(f"{platform}: {exc}")
            store.record_publication(job_id, platform, "failed", error=str(exc))
            store.event("error", "platform_failed", f"{platform} publication failed", job_id, error=str(exc))
    if failures:
        store.queue._transition(job_id, "failed", decision_note="; ".join(failures)[:2000])
        store.connection.execute(
            "UPDATE schedule_entries SET status='failed',note=?,updated_at=? WHERE job_id=? AND status='publishing'",
            ("; ".join(failures)[:1000], utc_now(), job_id),
        )
        store.connection.commit()
        notify(f"Yayın başarısız: {job['title'] or job['topic']}\n" + "\n".join(failures), "error", job_id)
        return False
    store.queue._transition(job_id, "published")
    store.connection.execute("UPDATE jobs SET published_at=?,updated_at=? WHERE id=?", (utc_now(), utc_now(), job_id))
    store.connection.execute("UPDATE schedule_entries SET status='published',updated_at=? WHERE job_id=? AND status IN ('planned','publishing')", (utc_now(), job_id))
    store.connection.commit()
    notify(f"Üçlü yayın tamamlandı: {job['title'] or job['topic']}", "success", job_id)
    return True


def process_due(store: ControlCenterStore) -> bool:
    live_enabled = (
        store.setting("publishing_enabled", "false") == "true"
        and os.environ.get("PUBLISH_ENABLED", "false").lower() == "true"
    )
    if not live_enabled:
        store.heartbeat("publisher-worker", "disabled", "Live publishing safety lock is on")
        return False
    row = store.connection.execute(
        """SELECT * FROM schedule_entries WHERE status='planned' AND job_id<>''
           AND scheduled_at<=? ORDER BY scheduled_at LIMIT 1""", (utc_now(),)
    ).fetchone()
    if not row:
        return False
    store.connection.execute("UPDATE schedule_entries SET status='publishing',updated_at=? WHERE id=?", (utc_now(), row["id"]))
    store.connection.commit()
    ok = publish_job(store, row["job_id"], row["platforms"])
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--job")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args()
    while True:
        store = ControlCenterStore(args.db)
        try:
            store.heartbeat("publisher-worker")
            if args.job:
                return 0 if publish_job(store, args.job) else 2
            processed = process_due(store)
        except Exception as exc:
            store.heartbeat("publisher-worker", "error", str(exc))
            store.event("error", "publisher_worker", str(exc))
            notify(f"Publisher worker hatası: {exc}", "error")
            processed = False
            if args.once:
                return 2
        finally:
            store.close()
        if args.once:
            return 0
        if not processed:
            time.sleep(max(5, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())

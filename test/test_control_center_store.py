from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from automation.control_center_store import ControlCenterStore
from automation.review_queue import QueueError


class ControlCenterStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = ControlCenterStore(Path(self.temp.name) / "queue.sqlite3")

    def tearDown(self) -> None:
        self.store.close()
        self.temp.cleanup()

    def pending_job(self, title: str = "A reason hidden in plain sight") -> dict:
        job = self.store.queue.create_job("test topic", title, "A test script")
        self.store.queue._transition(job["id"], "pending_review")
        return self.store.queue.get_job(job["id"])

    def test_defaults_create_four_weekly_slots_and_safe_publish_setting(self) -> None:
        slots = self.store.queue.list_weekly_slots()
        self.assertEqual([(x["weekday"], x["local_time"]) for x in slots], [
            (0, "22:30"), (2, "23:00"), (4, "22:00"), (6, "21:30")
        ])
        self.assertEqual(self.store.setting("publishing_enabled"), "false")

    def test_approve_adds_to_reserve_and_auto_assigns_to_schedule(self) -> None:
        job = self.pending_job()
        self.store.refresh_policy = lambda _job_id: {"status": "pass", "score": 90, "blockers": []}
        self.store.refresh_quality = lambda _job_id: {"status": "pass", "score": 90, "blockers": []}
        approved = self.store.approve(job["id"], human_confirmed=True)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["is_reserve"], 1)
        when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(timespec="seconds")
        self.store.schedule(job["id"], when)
        scheduled = self.store.schedules()
        self.assertEqual(scheduled[0]["job_id"], job["id"])
        self.assertEqual(self.store.job(job["id"])["is_reserve"], 0)

    def test_revision_preserves_original_and_creates_new_version(self) -> None:
        original = self.pending_job()
        revised = self.store.request_revision(original["id"], "visuals", "Use more Pexels clips")
        self.assertNotEqual(revised["id"], original["id"])
        self.assertEqual(revised["version"], 2)
        self.assertEqual(revised["parent_job_id"], original["id"])
        self.assertEqual(revised["review_action"], "visuals")
        self.assertEqual(revised["revision_note"], "Use more Pexels clips")
        self.assertEqual(self.store.job(original["id"])["status"], "held")
        self.assertEqual(
            [item["id"] for item in self.store.jobs(view_filter="pending")],
            [],
        )

    def test_rejecting_revision_cancels_every_unpublished_version(self) -> None:
        original = self.pending_job()
        revised = self.store.request_revision(original["id"], "visuals", "Try different footage")
        self.store.queue._transition(revised["id"], "rendering")
        result = self.store.reject(revised["id"], "Cancel this topic completely")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.store.job(original["id"])["status"], "rejected")

    def test_manual_schedule_limits_publication_to_one_video_per_day(self) -> None:
        first = self.pending_job("First")
        second = self.pending_job("Second")
        self.store.refresh_policy = lambda _job_id: {"status": "pass", "score": 90, "blockers": []}
        self.store.refresh_quality = lambda _job_id: {"status": "pass", "score": 90, "blockers": []}
        self.store.approve(first["id"], human_confirmed=True)
        self.store.approve(second["id"], human_confirmed=True)
        day = datetime.now(timezone.utc) + timedelta(days=3)
        self.store.schedule(first["id"], day.replace(hour=18, minute=0).isoformat(timespec="seconds"))
        with self.assertRaises(QueueError):
            self.store.schedule(second["id"], day.replace(hour=20, minute=0).isoformat(timespec="seconds"))

    def test_approval_requires_human_confirmation(self) -> None:
        job = self.pending_job()
        self.store.refresh_policy = lambda _job_id: {"status": "pass", "score": 90, "blockers": []}
        with self.assertRaises(QueueError):
            self.store.approve(job["id"], human_confirmed=False)

    def test_video_pool_views_group_internal_statuses_for_operator(self) -> None:
        pending = self.pending_job("Pending")
        failed = self.store.queue.create_job("failed topic", "Failed", "script")
        self.store.connection.execute(
            "UPDATE jobs SET status='failed' WHERE id=?", (failed["id"],),
        )
        self.store.connection.commit()
        self.assertEqual([item["id"] for item in self.store.jobs(view_filter="pending")], [pending["id"]])
        self.assertEqual([item["id"] for item in self.store.jobs(view_filter="rejected")], [failed["id"]])


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from automation.review_queue import ApprovalQueue, QueueError, validate_manifest


class ApprovalQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.queue = ApprovalQueue(self.root / "queue.sqlite3")

    def tearDown(self):
        self.queue.close()
        self.temp_dir.cleanup()

    def test_job_requires_human_review_before_approval(self):
        job = self.queue.create_job("Why manhole covers are round")
        self.assertEqual("draft", job["status"])
        with self.assertRaises(QueueError):
            self.queue.decide(job["id"], "approved")

    def test_rejected_job_can_return_to_draft(self):
        job = self.queue.create_job("Why keyboards are not alphabetical")
        self.queue._transition(job["id"], "rejected")
        self.queue._transition(job["id"], "draft")
        self.assertEqual("draft", self.queue.get_job(job["id"])["status"])

    def test_manifest_rejects_uncleared_assets(self):
        path = self.root / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "fact_sources": [{"url": "a"}, {"url": "b"}],
                    "assets": [
                        {
                            "type": "stock_video",
                            "source_url": "https://example.test/video",
                            "license": "unknown",
                            "commercial_use": False,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(QueueError):
            validate_manifest(path)

    def test_manifest_rejects_pending_ai_assets(self):
        path = self.root / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "fact_sources": [{"url": "a"}, {"url": "b"}],
                    "assets": [
                        {
                            "type": "ai_generated_image",
                            "source_url": "local://missing.png",
                            "license": "generated",
                            "commercial_use": True,
                            "generation_status": "pending",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(QueueError):
            validate_manifest(path)


if __name__ == "__main__":
    unittest.main()

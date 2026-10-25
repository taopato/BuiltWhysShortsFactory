from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from automation.control_center_store import ControlCenterStore
    from automation.review_queue import DEFAULT_DB
except ImportError:
    from control_center_store import ControlCenterStore
    from review_queue import DEFAULT_DB


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh and print BuiltWhys originality-policy reports.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--queue-visual-revisions", action="store_true")
    parser.add_argument("--cancel-revision", default="")
    args = parser.parse_args()
    store = ControlCenterStore(args.db)
    result = []
    try:
        if args.cancel_revision:
            revision = store.queue.get_job(args.cancel_revision)
            if revision["status"] not in {"revision_requested", "draft"} or not revision.get("parent_job_id"):
                raise SystemExit("Only a queued, not-yet-rendering revision can be cancelled")
            store.connection.execute(
                "UPDATE jobs SET status='rejected',decision_note='Cancelled: original already passed policy gate' WHERE id=?",
                (revision["id"],),
            )
            store.connection.execute(
                "UPDATE jobs SET status='pending_review',decision_note='',updated_at=? WHERE id=?",
                (revision["updated_at"], revision["parent_job_id"]),
            )
            store.connection.commit()
        for job in store.jobs():
            report = None
            if job.get("video_path") and job["status"] in {"pending_review", "approved", "held"}:
                report = store.refresh_policy(job["id"])
                current = store.queue.get_job(job["id"])
                existing_revision = store.connection.execute(
                    """SELECT 1 FROM jobs WHERE parent_job_id=?
                       AND status IN ('draft','rendering','revision_requested','pending_review') LIMIT 1""",
                    (job["id"],),
                ).fetchone()
                was_published = store.connection.execute(
                    "SELECT 1 FROM publications WHERE job_id=? AND status='published' LIMIT 1", (job["id"],),
                ).fetchone()
                if (args.queue_visual_revisions and report["status"] == "blocked"
                        and current["status"] in {"pending_review", "held", "approved"}
                        and not existing_revision and not was_published):
                    store.request_revision(
                        job["id"], "visuals",
                        "Automatic policy remediation: create six distinct Pexels scenes and original diagrams",
                    )
            current = store.queue.get_job(job["id"])
            result.append({
                "id": job["id"], "title": job.get("title") or job.get("topic"),
                "status": job["status"], "policy_status": current.get("policy_status"),
                "score": current.get("originality_score"),
                "blockers": report.get("blockers", []) if report else [],
            })
    finally:
        store.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

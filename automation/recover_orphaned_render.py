from __future__ import annotations

from control_center_store import ControlCenterStore
from review_queue import DEFAULT_DB, utc_now


store = ControlCenterStore(DEFAULT_DB)
try:
    rows = store.connection.execute("SELECT id FROM jobs WHERE status='rendering'").fetchall()
    for row in rows:
        store.connection.execute(
            "UPDATE jobs SET status='revision_requested',updated_at=? WHERE id=?",
            (utc_now(), row["id"]),
        )
        store.event("warning", "render_recovered", "Orphaned render returned to the queue", row["id"])
    store.connection.commit()
    print(f"recovered={len(rows)}")
finally:
    store.close()

from __future__ import annotations

import json
import sqlite3

from review_queue import DEFAULT_DB


connection = sqlite3.connect(DEFAULT_DB)
connection.row_factory = sqlite3.Row
queries = {
    "channels": "SELECT platform,captured_at,views,followers,media_count FROM channel_analytics_snapshots ORDER BY captured_at DESC LIMIT 10",
    "publications": "SELECT job_id,platform,status,remote_id FROM publications",
    "events": "SELECT level,kind,message,created_at FROM events WHERE kind LIKE 'analytics%' ORDER BY id DESC LIMIT 20",
    "recent_events": "SELECT level,kind,message,job_id,created_at FROM events ORDER BY id DESC LIMIT 20",
    "ready": "SELECT id,title,language,status,policy_status,quality_status,technical_score,story_id,source_job_id FROM jobs WHERE status IN ('approved','pending_review','rendering','revision_requested') ORDER BY updated_at DESC LIMIT 30",
    "blocked_reports": "SELECT id,policy_report,quality_report FROM jobs WHERE policy_status='blocked' OR quality_status='blocked' ORDER BY updated_at DESC LIMIT 3",
    "tables": "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
    "producer_heartbeat": "SELECT * FROM service_heartbeats WHERE service='producer-worker'",
}
print(json.dumps({name: [dict(row) for row in connection.execute(sql)] for name, sql in queries.items()}, ensure_ascii=False))

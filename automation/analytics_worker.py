from __future__ import annotations

import argparse
from datetime import date, timedelta
from difflib import SequenceMatcher
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

from control_center_store import ControlCenterStore
from google_auth import headers
from review_queue import DEFAULT_DB, utc_now


def insert(store: ControlCenterStore, job_id: str, platform: str, values: dict[str, Any], raw: Any) -> None:
    store.connection.execute(
        """INSERT INTO analytics_snapshots(job_id,platform,captured_at,views,likes,comments,shares,saves,
           watch_seconds,average_view_percentage,followers_gained,raw_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (job_id, platform, utc_now(), int(values.get("views", 0)), int(values.get("likes", 0)),
         int(values.get("comments", 0)), int(values.get("shares", 0)), int(values.get("saves", 0)),
         float(values.get("watch_seconds", 0)), float(values.get("average_view_percentage", 0)),
         int(values.get("followers_gained", 0)), json.dumps(raw, ensure_ascii=False)),
    )
    store.connection.commit()


def insert_channel(store: ControlCenterStore, platform: str, values: dict[str, Any], raw: Any) -> None:
    store.connection.execute(
        """INSERT INTO channel_analytics_snapshots(
           platform,captured_at,views,followers,media_count,raw_json)
           VALUES (?,?,?,?,?,?)""",
        (platform, utc_now(), int(values.get("views", 0)), int(values.get("followers", 0)),
         int(values.get("media_count", 0)), json.dumps(raw, ensure_ascii=False)),
    )
    store.connection.commit()


def insert_geo(store: ControlCenterStore, platform: str, period_days: int,
               rows: list[dict[str, Any]], raw: Any) -> None:
    """Store one coherent geographic snapshot for the analytics screen."""
    captured_at = utc_now()
    store.connection.executemany(
        """INSERT INTO geo_analytics_snapshots(
           platform,captured_at,period_days,country,views,watch_seconds,likes,comments,shares,raw_json)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [
            (platform, captured_at, period_days, str(row.get("country") or "ZZ"),
             int(row.get("views", 0)), float(row.get("estimatedMinutesWatched", 0)) * 60,
             int(row.get("likes", 0)), int(row.get("comments", 0)), int(row.get("shares", 0)),
             json.dumps({"row": row, "report": raw.get("columnHeaders", [])}, ensure_ascii=False))
            for row in rows
        ],
    )
    # Retain enough history for diagnostics without letting four snapshots per day grow forever.
    store.connection.execute(
        """DELETE FROM geo_analytics_snapshots WHERE platform=? AND captured_at < datetime('now','-120 days')""",
        (platform,),
    )
    store.connection.commit()


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _safe_error(exc: Exception) -> str:
    """Never persist OAuth or platform tokens embedded in request exception URLs."""
    value = str(exc)
    value = re.sub(r"([?&]access_token=)[^&\s]+", r"\1[redacted]", value)
    return value[:1200]


def _match_job(store: ControlCenterStore, video_id: str, title: str) -> str:
    linked = store.connection.execute(
        "SELECT job_id FROM publications WHERE platform='youtube' AND remote_id=? LIMIT 1", (video_id,),
    ).fetchone()
    if linked:
        return str(linked["job_id"])
    candidates = [dict(row) for row in store.connection.execute(
        """SELECT id,title,topic FROM jobs WHERE language='en-US'
           AND status IN ('approved','pending_review','held','published')
           AND NOT EXISTS (SELECT 1 FROM publications p WHERE p.job_id=jobs.id
                           AND p.platform='youtube' AND p.remote_id<>'')"""
    )]
    if not candidates:
        return ""
    wanted = _normalized(title)
    ranked = sorted(
        ((max(SequenceMatcher(None, wanted, _normalized(item.get("title") or "")).ratio(),
              SequenceMatcher(None, wanted, _normalized(item.get("topic") or "")).ratio()), item)
         for item in candidates), reverse=True, key=lambda pair: pair[0],
    )
    score, match = ranked[0]
    # A single legacy manual upload is safe to associate even when its final
    # YouTube title differs from the internal working title.
    if score < 0.45 and len(candidates) != 1:
        return ""
    store.connection.execute(
        """INSERT INTO publications(job_id,platform,status,remote_id,remote_url,error,attempts,
           published_at,updated_at) VALUES (?,'youtube','published',?,?, '',0,?,?)
           ON CONFLICT(job_id,platform) DO UPDATE SET status='published',remote_id=excluded.remote_id,
           remote_url=excluded.remote_url,updated_at=excluded.updated_at""",
        (match["id"], video_id, f"https://www.youtube.com/shorts/{video_id}", utc_now(), utc_now()),
    )
    store.connection.commit()
    store.event("info", "analytics_linked", f"Matched YouTube video: {title}", match["id"],
                remote_id=video_id, similarity=round(score, 3))
    return str(match["id"])


def youtube_channel(store: ControlCenterStore) -> int:
    auth = headers()
    channel_response = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "statistics", "mine": "true"}, headers=auth, timeout=30,
    )
    channel_response.raise_for_status()
    channel_payload = channel_response.json()
    channel_stats = ((channel_payload.get("items") or [{}])[0]).get("statistics", {})
    insert_channel(store, "youtube", {
        "views": channel_stats.get("viewCount", 0),
        "followers": channel_stats.get("subscriberCount", 0),
        "media_count": channel_stats.get("videoCount", 0),
    }, channel_payload)

    end = date.today()
    start = end - timedelta(days=90)
    report_response = requests.get(
        "https://youtubeanalytics.googleapis.com/v2/reports",
        params={
            "ids": "channel==MINE", "startDate": start.isoformat(), "endDate": end.isoformat(),
            "dimensions": "video",
            "metrics": "views,likes,comments,shares,estimatedMinutesWatched,averageViewPercentage,subscribersGained",
            "sort": "-views", "maxResults": 200,
        }, headers=auth, timeout=30,
    )
    report_response.raise_for_status()
    report = report_response.json()
    columns = [item["name"] for item in report.get("columnHeaders", [])]
    rows = [dict(zip(columns, row)) for row in report.get("rows", [])]

    geo_params = {
        "ids": "channel==MINE", "startDate": start.isoformat(), "endDate": end.isoformat(),
        "dimensions": "country",
        "metrics": "views,likes,comments,shares,estimatedMinutesWatched",
        "sort": "-views", "maxResults": 200,
    }
    geo_response = requests.get(
        "https://youtubeanalytics.googleapis.com/v2/reports",
        params=geo_params, headers=auth, timeout=30,
    )
    # Some very new channels temporarily expose only viewing metrics by geography.
    if geo_response.status_code == 400:
        geo_params["metrics"] = "views,estimatedMinutesWatched"
        geo_response = requests.get(
            "https://youtubeanalytics.googleapis.com/v2/reports",
            params=geo_params, headers=auth, timeout=30,
        )
    geo_response.raise_for_status()
    geo_report = geo_response.json()
    geo_columns = [item["name"] for item in geo_report.get("columnHeaders", [])]
    geo_rows = [dict(zip(geo_columns, row)) for row in geo_report.get("rows", [])]
    insert_geo(store, "youtube", 90, geo_rows, geo_report)
    if not rows:
        return 0
    ids = [str(row["video"]) for row in rows]
    details_response = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics", "id": ",".join(ids[:50])}, headers=auth, timeout=30,
    )
    details_response.raise_for_status()
    details = {item["id"]: item for item in details_response.json().get("items", [])}
    count = 0
    for row in rows:
        video_id = str(row["video"])
        item = details.get(video_id, {})
        title = str(item.get("snippet", {}).get("title") or video_id)
        job_id = _match_job(store, video_id, title)
        if not job_id:
            store.event("warning", "analytics_unmatched", f"Unmatched YouTube video: {title}",
                        remote_id=video_id)
            continue
        insert(store, job_id, "youtube", {
            "views": row.get("views", 0), "likes": row.get("likes", 0),
            "comments": row.get("comments", 0), "shares": row.get("shares", 0),
            "watch_seconds": float(row.get("estimatedMinutesWatched", 0)) * 60,
            "average_view_percentage": row.get("averageViewPercentage", 0),
            "followers_gained": row.get("subscribersGained", 0),
        }, {"analytics": row, "video": item})
        count += 1
    return count


def youtube(store: ControlCenterStore, publication: dict[str, Any]) -> None:
    response = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "statistics", "id": publication["remote_id"]}, headers=headers(), timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    stats = (payload.get("items") or [{}])[0].get("statistics", {})
    insert(store, publication["job_id"], "youtube", {
        "views": stats.get("viewCount", 0), "likes": stats.get("likeCount", 0),
        "comments": stats.get("commentCount", 0),
    }, payload)


def meta(store: ControlCenterStore, publication: dict[str, Any]) -> None:
    token = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
    version = os.environ.get("META_GRAPH_VERSION", "v25.0")
    is_instagram = publication["platform"] == "instagram"
    fields = "like_count,comments_count" if is_instagram else "views,likes.limit(0).summary(true),comments.limit(0).summary(true)"
    response = requests.get(
        f"https://graph.facebook.com/{version}/{publication['remote_id']}",
        params={"fields": fields, "access_token": token}, timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if is_instagram:
        values = {"likes": payload.get("like_count", 0), "comments": payload.get("comments_count", 0)}
        insight = requests.get(
            f"https://graph.facebook.com/{version}/{publication['remote_id']}/insights",
            params={"metric": "views,reach,saved,shares,total_interactions", "access_token": token}, timeout=30,
        )
        if insight.ok:
            insight_payload = insight.json()
            for metric in insight_payload.get("data", []):
                value = ((metric.get("values") or [{}])[-1]).get("value", 0)
                name = metric.get("name")
                if name == "views": values["views"] = value
                elif name == "saved": values["saves"] = value
                elif name == "shares": values["shares"] = value
            payload["insights"] = insight_payload
        else:
            payload["insights_unavailable"] = True
    else:
        values = {
            "views": payload.get("views", 0),
            "likes": payload.get("likes", {}).get("summary", {}).get("total_count", 0),
            "comments": payload.get("comments", {}).get("summary", {}).get("total_count", 0),
        }
    insert(store, publication["job_id"], publication["platform"], values, payload)


def meta_channels(store: ControlCenterStore) -> int:
    token = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
    version = os.environ.get("META_GRAPH_VERSION", "v25.0")
    page_id = os.environ.get("META_PAGE_ID", "")
    instagram_id = os.environ.get("META_IG_USER_ID", "")
    if not token:
        return 0
    count = 0
    if page_id:
        response = requests.get(
            f"https://graph.facebook.com/{version}/{page_id}",
            params={"fields": "followers_count,fan_count", "access_token": token}, timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        insert_channel(store, "facebook", {"followers": payload.get("followers_count") or payload.get("fan_count", 0)}, payload)
        count += 1
    if instagram_id:
        response = requests.get(
            f"https://graph.facebook.com/{version}/{instagram_id}",
            params={"fields": "followers_count,media_count", "access_token": token}, timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        insert_channel(store, "instagram", {
            "followers": payload.get("followers_count", 0), "media_count": payload.get("media_count", 0),
        }, payload)
        count += 1
    return count


def collect(store: ControlCenterStore) -> int:
    count = 0
    try:
        count += youtube_channel(store)
    except Exception as exc:
        store.event("warning", "analytics_failed", f"youtube channel analytics: {_safe_error(exc)}")
    try:
        count += meta_channels(store)
    except Exception as exc:
        store.event("warning", "analytics_failed", f"meta channel analytics: {_safe_error(exc)}")
    rows = store.connection.execute("SELECT * FROM publications WHERE status='published' AND remote_id<>''").fetchall()
    for row in rows:
        publication = dict(row)
        try:
            # YouTube rows are collected through the Analytics report above,
            # which also repairs IDs for legacy manual uploads.
            if publication["platform"] != "youtube":
                meta(store, publication)
            count += 1
        except Exception as exc:
            store.event("warning", "analytics_failed", f"{publication['platform']} analytics: {_safe_error(exc)}", publication["job_id"])
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=21600)
    args = parser.parse_args()
    while True:
        store = ControlCenterStore(args.db)
        try:
            count = collect(store)
            store.heartbeat("analytics-worker", detail=f"updated={count}")
        except Exception as exc:
            store.heartbeat("analytics-worker", "error", str(exc))
        finally:
            store.close()
        if args.once:
            return 0
        time.sleep(max(900, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())

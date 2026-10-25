from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

from google_auth import GoogleAuthError, headers


class YouTubeError(RuntimeError):
    pass


def _payload(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise YouTubeError(f"YouTube returned HTTP {response.status_code} without JSON") from exc
    if not response.ok:
        raise YouTubeError(f"YouTube API error ({response.status_code}): {data}")
    return data


def publish(video_path: Path, title: str, description: str, hashtags: str = "",
            thumbnail_path: Path | None = None, privacy: str = "private",
            language: str = "en-US") -> tuple[str, str]:
    if not video_path.is_file():
        raise YouTubeError("video file does not exist")
    if privacy not in {"private", "unlisted", "public"}:
        raise YouTubeError("privacy must be private, unlisted or public")
    if privacy != "private" and os.environ.get("YOUTUBE_API_AUDIT_APPROVED", "false").lower() != "true":
        raise YouTubeError("public/unlisted API upload is locked until the YouTube API compliance audit is approved")
    tags = [item.strip().lstrip("#") for item in hashtags.replace(",", " ").split() if item.strip()]
    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": os.environ.get("YOUTUBE_CATEGORY_ID", "28"),
            "defaultLanguage": "tr" if language == "tr-TR" else "en",
            "defaultAudioLanguage": "tr" if language == "tr-TR" else "en",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    auth = headers(language)
    start = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            **auth,
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
            "X-Upload-Content-Type": "video/mp4",
        },
        data=json.dumps(metadata), timeout=60,
    )
    if not start.ok or not start.headers.get("Location"):
        raise YouTubeError(f"YouTube resumable upload could not start: {start.text[:1000]}")
    with video_path.open("rb") as video:
        result = requests.put(
            start.headers["Location"], data=video,
            headers={"Content-Type": "video/mp4", "Content-Length": str(video_path.stat().st_size)},
            timeout=1200,
        )
    data = _payload(result)
    video_id = str(data["id"])
    if thumbnail_path and thumbnail_path.is_file():
        with thumbnail_path.open("rb") as image:
            requests.post(
                "https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                params={"videoId": video_id, "uploadType": "media"},
                headers={**auth, "Content-Type": "image/jpeg"}, data=image, timeout=120,
            )
    return video_id, f"https://www.youtube.com/shorts/{video_id}"


__all__ = ["publish", "YouTubeError", "GoogleAuthError"]

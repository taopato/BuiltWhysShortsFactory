from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

from google_auth import headers
from youtube_publish import publish


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    output = ROOT / "storage" / "qa" / "youtube-private-oauth-test.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x111827:s=720x1280:d=2",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
            str(output),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.environ["YOUTUBE_PRIVACY_STATUS"] = "private"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    video_id, url = publish(
        output,
        f"[PRIVATE TEST] BuiltWhys Automation - {stamp}",
        "Private OAuth and upload pipeline test. This is not a public BuiltWhys Short.",
    )
    response = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,status", "id": video_id},
        headers=headers(),
        timeout=30,
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    if not items:
        raise RuntimeError("YouTube did not return the uploaded private test video")
    video = items[0]
    privacy = video.get("status", {}).get("privacyStatus", "")
    if privacy != "private":
        raise RuntimeError(f"Safety check failed: expected private, received {privacy!r}")
    print(json.dumps({
        "ok": True,
        "video_id": video_id,
        "url": url,
        "privacy": privacy,
        "channel_id": video.get("snippet", {}).get("channelId", ""),
        "title": video.get("snippet", {}).get("title", ""),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

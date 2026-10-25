from __future__ import annotations

import json
import math
import os
import struct
import subprocess
import sys
import wave
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "pilots" / "satisfying-machines"
CLIPS = (
    (29464201, "industrial grinding with sparks"),
    (7480059, "CNC machining"),
    (8063941, "clay slicing"),
    (6666438, "orange slicing"),
    (37175111, "pressure washing"),
    (33568935, "watercolor mixing"),
)
SEGMENT_SECONDS = 4.2


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def pexels_video(video_id: int) -> tuple[str, str, str]:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PEXELS_API_KEY is required")
    response = requests.get(
        f"https://api.pexels.com/videos/videos/{video_id}",
        headers={"Authorization": key}, timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    files = [item for item in data.get("video_files", []) if item.get("link")]
    portrait = [item for item in files if int(item.get("height") or 0) > int(item.get("width") or 0)]
    candidates = portrait or files
    candidates.sort(key=lambda item: (
        abs(int(item.get("width") or 0) - 1080),
        abs(int(item.get("height") or 0) - 1920),
    ))
    if not candidates:
        raise RuntimeError(f"No downloadable file for Pexels video {video_id}")
    return candidates[0]["link"], data.get("url", ""), data.get("user", {}).get("name", "Pexels creator")


def download(url: str, path: Path) -> None:
    if path.is_file() and path.stat().st_size > 100_000:
        return
    with requests.get(url, stream=True, timeout=90) as response:
        response.raise_for_status()
        with path.open("wb") as output:
            for block in response.iter_content(1024 * 1024):
                if block:
                    output.write(block)


def sound_design(path: Path, duration: float) -> None:
    rate = 44_100
    boundaries = [SEGMENT_SECONDS * i for i in range(1, len(CLIPS))]
    with wave.open(str(path), "wb") as output:
        output.setparams((2, 2, rate, int(duration * rate), "NONE", "not compressed"))
        for index in range(int(duration * rate)):
            second = index / rate
            pulse = 0.025 * math.sin(2 * math.pi * 55 * second)
            pulse += 0.012 * math.sin(2 * math.pi * 110 * second)
            for moment in boundaries:
                distance = second - moment
                if 0 <= distance < 0.18:
                    envelope = 1 - distance / 0.18
                    pulse += 0.25 * envelope * math.sin(2 * math.pi * (120 - distance * 300) * distance)
            shimmer = 0.0
            if second < SEGMENT_SECONDS * 2:
                shimmer = 0.018 * math.sin(2 * math.pi * 880 * second)
            value = int(max(-1, min(1, pulse + shimmer)) * 32767)
            output.writeframesraw(struct.pack("<hh", value, value))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    normalized: list[Path] = []
    manifest: list[dict[str, str | int]] = []
    for order, (video_id, purpose) in enumerate(CLIPS, 1):
        url, source_url, creator = pexels_video(video_id)
        raw = OUT / f"raw-{order:02d}.mp4"
        clip = OUT / f"clip-{order:02d}.mp4"
        download(url, raw)
        start = 0.25 if order != 2 else 2.0
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(start), "-i", str(raw), "-t", str(SEGMENT_SECONDS),
            "-an", "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,fps=30,eq=contrast=1.08:saturation=1.10,"
            "unsharp=5:5:0.45:5:5:0,fade=t=in:st=0:d=0.10,"
            f"fade=t=out:st={SEGMENT_SECONDS - 0.10}:d=0.10,"
            "drawbox=x=55:y=1845:w=970:h=7:color=white@0.18:t=fill,"
            f"drawbox=x=55:y=1845:w={int(970 * order / len(CLIPS))}:h=7:color=white@0.80:t=fill,"
            "drawtext=text='BW':x=58:y=58:fontsize=38:fontcolor=white@0.72:"
            "box=1:boxcolor=black@0.30:boxborderw=14",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(clip),
        ])
        normalized.append(clip)
        manifest.append({
            "pexels_id": video_id, "purpose": purpose, "source_url": source_url,
            "creator": creator, "license": "Pexels License", "commercial_use": "yes",
        })

    concat = OUT / "concat.txt"
    concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in normalized), encoding="utf-8")
    silent = OUT / "silent.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat), "-c", "copy", str(silent)])
    duration = SEGMENT_SECONDS * len(CLIPS)
    audio = OUT / "original-sound-design.wav"
    sound_design(audio, duration)
    final = OUT / "machines-vs-materials-pilot.mp4"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent), "-i", str(audio),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final),
    ])
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.7", "-i", str(final),
         "-frames:v", "1", "-q:v", "2", str(OUT / "thumbnail.jpg")])
    (OUT / "manifest.json").write_text(json.dumps({
        "title": "Machines vs Materials — Satisfying Test",
        "language_free": True,
        "editing": "Original BuiltWhys sequence, grading, pacing, progress graphics and sound design",
        "assets": manifest,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(final)
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import json
import math
import random
import struct
import subprocess
import sys
import wave
from pathlib import Path

from render_satisfying_pilot import ROOT, download, pexels_video, run


OUT = ROOT / "storage" / "pilots" / "single-story-wheel"
# One creator, one SUV wheel, one continuous cleaning story.
STORY = (
    (37175109, 0.0, 8.0, "dirty wheel and first cleaning pass"),
    (37175111, 3.5, 8.0, "pressure wash"),
    (37175110, 0.5, 9.0, "tire dressing and finishing"),
    (37175110, 14.0, 5.0, "finished wheel reveal"),
)


def sound_design(path: Path, duration: float) -> None:
    rate = 44_100
    rng = random.Random(37175109)
    with wave.open(str(path), "wb") as output:
        output.setparams((2, 2, rate, int(duration * rate), "NONE", "not compressed"))
        smooth_noise = 0.0
        for index in range(int(duration * rate)):
            second = index / rate
            smooth_noise = smooth_noise * 0.88 + rng.uniform(-1, 1) * 0.12
            if second < 8:
                texture = 0.035 * smooth_noise + 0.012 * math.sin(2 * math.pi * 90 * second)
            elif second < 16:
                texture = 0.095 * smooth_noise + 0.025 * math.sin(2 * math.pi * 62 * second)
            elif second < 25:
                texture = 0.026 * smooth_noise + 0.008 * math.sin(2 * math.pi * 120 * second)
            else:
                texture = 0.012 * math.sin(2 * math.pi * 110 * second)
            reveal_distance = second - 25.2
            if 0 <= reveal_distance < 0.8:
                texture += 0.12 * (1 - reveal_distance / 0.8) * math.sin(
                    2 * math.pi * (660 + 220 * reveal_distance) * reveal_distance
                )
            value = int(max(-1, min(1, texture)) * 32767)
            output.writeframesraw(struct.pack("<hh", value, value))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    assets: list[dict[str, object]] = []
    elapsed = 0.0
    for order, (video_id, start, length, purpose) in enumerate(STORY, 1):
        url, source_url, creator = pexels_video(video_id)
        raw = OUT / f"raw-{video_id}.mp4"
        clip = OUT / f"story-{order:02d}.mp4"
        download(url, raw)
        symbol = ""
        if order == 1:
            symbol = ",drawtext=text='?':x=(w-text_w)/2:y=150:fontsize=120:fontcolor=white@0.90:box=1:boxcolor=black@0.22:boxborderw=18"
        elif order == len(STORY):
            symbol = ",drawtext=text='✓':x=(w-text_w)/2:y=145:fontsize=110:fontcolor=0x4cdb92@0.95:box=1:boxcolor=black@0.22:boxborderw=18"
        progress = min(1.0, (elapsed + length) / sum(item[2] for item in STORY))
        vf = (
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,"
            "eq=contrast=1.08:saturation=1.08,unsharp=5:5:0.40:5:5:0,"
            "fade=t=in:st=0:d=0.10," +
            f"fade=t=out:st={length - 0.10}:d=0.10,"
            "drawbox=x=55:y=1845:w=970:h=7:color=white@0.16:t=fill," +
            f"drawbox=x=55:y=1845:w={int(970 * progress)}:h=7:color=0x4cdb92@0.82:t=fill,"
            "drawtext=text='BW':x=58:y=58:fontsize=38:fontcolor=white@0.70:"
            "box=1:boxcolor=black@0.28:boxborderw=14" + symbol
        )
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start),
            "-i", str(raw), "-t", str(length), "-an", "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(clip),
        ])
        elapsed += length
        clips.append(clip)
        if not any(item["pexels_id"] == video_id for item in assets):
            assets.append({
                "pexels_id": video_id, "creator": creator, "source_url": source_url,
                "license": "Pexels License", "commercial_use": True,
            })

    concat = OUT / "concat.txt"
    concat.write_text("".join(f"file '{path.as_posix()}'\n" for path in clips), encoding="utf-8")
    silent = OUT / "silent.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(concat), "-c", "copy", str(silent)])
    duration = sum(item[2] for item in STORY)
    audio = OUT / "original-sound-design.wav"
    sound_design(audio, duration)
    final = OUT / "will-this-wheel-look-new-again.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent), "-i", str(audio),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final)])
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.8", "-i", str(final),
         "-frames:v", "1", "-q:v", "2", str(OUT / "thumbnail.jpg")])
    (OUT / "manifest.json").write_text(json.dumps({
        "title": "Will This Wheel Look New Again?",
        "language_free": True,
        "story": "One dirty wheel, one cleaning process, one final reveal",
        "editing": "Original BuiltWhys story structure, grading, progress graphics and sound design",
        "assets": assets,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(final)
    return 0


if __name__ == "__main__":
    sys.exit(main())

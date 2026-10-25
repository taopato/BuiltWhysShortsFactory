"""One-command, non-publishing render of the BuiltWhys tape-measure 3D pilot.

Requires Blender and FFmpeg executables and an existing BuiltWhys narration
folder with audio.mp3 and subtitle.srt. This script has no publisher imports.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "storage" / "3d-pilots"


def binary(name: str, override: str | None) -> str:
    value = override or shutil.which(name)
    if not value or not Path(value).is_file():
        raise SystemExit(f"{name} is unavailable; provide --{name}-bin")
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-task-dir", type=Path, required=True)
    parser.add_argument("--blender-bin", default=os.getenv("BLENDER_BIN"))
    parser.add_argument("--ffmpeg-bin", default=os.getenv("FFMPEG_BIN"))
    parser.add_argument("--reuse-frames", action="store_true")
    args = parser.parse_args()
    source = args.source_task_dir.resolve()
    for expected in ("audio.mp3", "subtitle.srt"):
        if not (source / expected).is_file():
            raise SystemExit(f"Missing narration input: {source / expected}")
    blender = binary("blender", args.blender_bin)
    ffmpeg = binary("ffmpeg", args.ffmpeg_bin)
    frames = OUT / "tape-frames"
    if not args.reuse_frames:
        subprocess.run([blender, "--background", "--python", str(HERE / "tape_story.py"), "--", "render"], check=True)
    count = len(list(frames.glob("frame_*.png")))
    if count != 810 or not (frames / "frame_0001.png").is_file() or not (frames / "frame_0810.png").is_file():
        raise SystemExit(f"Incomplete 3D render: expected 810 frames, found {count}")
    env = os.environ.copy()
    env["PATH"] = str(Path(ffmpeg).parent) + os.pathsep + env.get("PATH", "")
    subprocess.run(
        [sys.executable, str(HERE / "compose_pilot.py"), "tape", "--source-task-dir", str(source)],
        env=env,
        check=True,
    )
    result = OUT / "builtwhys-tape-3d-pilot.mp4"
    subprocess.run([ffmpeg, "-v", "error", "-i", str(result), "-f", "null", os.devnull], check=True)
    print(f"Review only; not queued for publishing: {result}")


if __name__ == "__main__":
    main()

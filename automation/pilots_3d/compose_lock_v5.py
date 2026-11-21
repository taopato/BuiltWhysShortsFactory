"""Assemble a review-only lock pilot using the new causal pin shot.

The original 36-second narration and human/door context remain in the prior
review pilot. Seconds 10.1–15.1 are replaced by a server-rendered cutaway.
No upload or approval state is touched.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--ass", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    options = parser.parse_args()
    source = options.workdir / "lock-cinematic-pilot-v4.mp4"
    frames = options.workdir / "frames"
    output = options.workdir / "lock-causal-hybrid-v5-review.mp4"
    expected = [frames / f"frame_{number:04d}.png" for number in range(120)]
    missing = [path for path in expected if not path.is_file() or path.stat().st_size < 10000]
    if not source.is_file() or missing or not options.ass.is_file():
        raise SystemExit(f"missing source, captions, or {len(missing)} rendered frames")
    graph = (
        "[0:v]trim=start=0:end=10.1,setpts=PTS-STARTPTS[v0];"
        f"[1:v]ass={options.ass},trim=duration=5,setpts=PTS-STARTPTS[v1];"
        "[0:v]trim=start=15.1:end=36,setpts=PTS-STARTPTS[v2];"
        "[v0][v1][v2]concat=n=3:v=1:a=0[v]"
    )
    subprocess.run(
        [options.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(source), "-framerate", "24", "-start_number", "0",
         "-i", str(frames / "frame_%04d.png"), "-filter_complex", graph,
         "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium",
         "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", str(output)],
        check=True,
    )
    probe = subprocess.run(
        [options.ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(output)], check=True, capture_output=True, text=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])
    if not 35.9 <= duration <= 36.1:
        raise SystemExit(f"unexpected output duration: {duration}")
    print(f"REVIEW_VIDEO={output}\nDURATION={duration:.2f}")


if __name__ == "__main__":
    main()

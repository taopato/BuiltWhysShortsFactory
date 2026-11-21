"""Render an isolated proof-of-motion range at controlled CPU cost.

The existing scene is loaded by Blender before this script runs. Output frames
are numbered consecutively for ffmpeg, while source-frame numbers are logged.
No production database, worker, or publisher is accessed.
"""

import argparse
import sys
import time
from pathlib import Path

import bpy


def main() -> None:
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--step", type=int, default=2)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args(args)
    if options.start < 1 or options.end < options.start or options.step < 1:
        parser.error("invalid frame range")
    if options.end - options.start > 120 or options.samples not in (8, 16, 32, 64):
        parser.error("pilot render limited to 120 source frames and 8–64 samples")
    options.out.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.eevee.taa_render_samples = options.samples
    began = time.monotonic()
    for index, source_frame in enumerate(range(options.start, options.end + 1, options.step)):
        destination = options.out / f"frame_{index:04d}.png"
        if destination.exists() and destination.stat().st_size > 10000:
            print(f"SKIP {source_frame} -> {destination}", flush=True)
            continue
        scene.frame_set(source_frame)
        scene.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {source_frame} -> {destination}", flush=True)
    print(f"RANGE_SECONDS={time.monotonic() - began:.2f}", flush=True)


if __name__ == "__main__":
    main()

"""Render one isolated low-priority 3D pilot frame; never touches the queue."""

import argparse
import time
from pathlib import Path

import bpy


def main() -> None:
    argv = __import__("sys").argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", type=int, default=365)
    parser.add_argument("--scale", type=int, default=50)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args(args)
    if options.scale < 25 or options.scale > 100:
        parser.error("scale must be 25–100")
    if options.samples < 1 or options.samples > 128:
        parser.error("samples must be 1–128")
    scene = bpy.context.scene
    scene.render.resolution_percentage = options.scale
    if scene.render.engine == "BLENDER_EEVEE_NEXT":
        scene.eevee.taa_render_samples = options.samples
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(options.out)
    scene.frame_set(options.frame)
    started = time.monotonic()
    bpy.ops.render.render(write_still=True)
    print(f"FRAME_SECONDS={time.monotonic() - started:.2f}")
    print(f"FRAME_OUTPUT={options.out}")


if __name__ == "__main__":
    main()

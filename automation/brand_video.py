from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_WATERMARK = (
    ROOT_DIR / "automation" / "branding" / "builtwhys-watermark-white-v1.png"
)
DEFAULT_FONT = ROOT_DIR / "resource" / "fonts" / "BeVietnamPro-Bold.ttf"


def _filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")


def brand_video(
    video_path: Path,
    watermark_path: Path = DEFAULT_WATERMARK,
    font_path: Path = DEFAULT_FONT,
    cover_text: str = "BUILT DIFFERENT",
) -> Path:
    """Add the BuiltWhys mark, a selectable opening cover, and mobile loudness."""
    video = Path(video_path).resolve()
    watermark = Path(watermark_path).resolve()
    font = Path(font_path).resolve()
    for required in (video, watermark, font):
        if not required.is_file():
            raise FileNotFoundError(f"branding input not found: {required}")
    cover_text = cover_text.strip().upper()
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ?!-"
    if not cover_text or len(cover_text) > 36 or any(character not in allowed for character in cover_text):
        raise ValueError("cover_text must use 1-36 safe uppercase characters")

    temporary = video.with_name(f"{video.stem}.branded{video.suffix}")
    filter_graph = (
        "[1:v]scale=150:-1:flags=lanczos,format=rgba,"
        "colorchannelmixer=aa=0.76[wm];"
        "[0:v][wm]overlay=48:72[base];"
        f"[base]drawtext=fontfile='{_filter_path(font)}':"
        f"text='{cover_text}':fontcolor=white:fontsize=78:"
        "borderw=4:bordercolor=black@0.8:"
        "x=(w-text_w)/2:y=h*0.24:enable='between(t,0,0.9)'[vraw];"
        "[vraw]scale=1080:1920:flags=lanczos,setsar=1[v]"
    )
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-i",
        str(watermark),
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        "-map",
        "0:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "19",
        "-af",
        "loudnorm=I=-16:LRA=7:TP=-1.5",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-metadata:s:v:0",
        "rotate=0",
        "-movflags",
        "+faststart",
        "-y",
        str(temporary),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        os.replace(temporary, video)
    except subprocess.CalledProcessError as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"video branding failed: {exc.stderr.strip()}") from exc
    return video

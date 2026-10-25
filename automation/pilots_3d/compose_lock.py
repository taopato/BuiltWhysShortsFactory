"""Compose the original lock cutaway pilot; never uploads or schedules it.

This local-only proof of concept intentionally does not reuse a third-party
voice. A production narration must be generated separately before approval.
"""

from __future__ import annotations

import math
import random
import struct
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "storage" / "3d-pilots"
FONT_DIR = ROOT / "resource" / "fonts"
DURATION = 30.0

BEATS = [
    (0.0, 2.9, "WHAT'S INSIDE?", "A key does more than turn a cylinder."),
    (2.9, 5.7, "FIVE PIN PAIRS", "Springs push paired pins into the plug."),
    (5.7, 8.0, "WRONG KEY", "The pin seams stop at different heights."),
    (8.0, 10.9, "PLUG BLOCKED", "One driver pin crossing the line is enough."),
    (10.9, 15.5, "RIGHT KEY", "Each cut raises a different pin."),
    (15.5, 19.0, "ONE SHEAR LINE", "All five pin seams now line up."),
    (19.0, 21.6, "NOW IT TURNS", "The plug is free to rotate."),
    (21.6, 24.3, "MOTION TO THE CAM", "Rotation moves the cam at the back."),
    (24.3, 27.1, "BOLT RETRACTS", "The cam draws the bolt away."),
    (27.1, 30.0, "UNLOCKED", "A small key coordinates the mechanism."),
]


def ts(s: float) -> str:
    return f"0:00:{s:05.2f}"


def ass_text(s: str) -> str:
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def write_ass() -> Path:
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 720", "PlayResY: 1280", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Brand,Be Vietnam Pro,19,&H00FFFFFF,&H00FFFFFF,&H00071929,&H00000000,0,0,0,0,100,100,1,0,1,1,0,7,50,50,48,1",
        "Style: Title,Be Vietnam Pro,49,&H00FFFFFF,&H00FFFFFF,&H00071929,&H00000000,-1,0,0,0,100,100,0,0,1,2,1,8,42,42,110,1",
        "Style: Caption,Be Vietnam Pro,34,&H00FFFFFF,&H00FFFFFF,&H00071929,&H7A071929,0,0,0,0,100,100,0,0,3,1,0,2,53,53,246,1",
        "Style: Footer,Be Vietnam Pro,16,&H0099ADC2,&H00FFFFFF,&H00071929,&H00000000,0,0,0,0,100,100,0,0,1,0,0,1,49,49,55,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        "Dialogue: 0,0:00:00.00,0:00:30.00,Brand,,0,0,0,,BUILTWHYS  /  HOW IT WORKS",
        "Dialogue: 0,0:00:00.00,0:00:30.00,Footer,,0,0,0,,ORIGINAL 3D EXPLAINER  •  PILOT",
    ]
    for start, end, title, caption in BEATS:
        lines.append(f"Dialogue: 1,{ts(start)},{ts(end)},Title,,0,0,0,,{ass_text(title)}")
        lines.append(f"Dialogue: 2,{ts(start)},{ts(end)},Caption,,0,0,0,,{ass_text(caption)}")
    path = OUT / "lock.ass"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_soundtrack() -> Path:
    """Produce subtle, entirely synthetic mechanism ticks and a low drone."""
    rate = 24_000
    random.seed(17)
    events = [(0.1, 150), (3.0, 135), (5.8, 170), (8.0, 200), (11.0, 100)]
    events += [(12.0 + i * 0.56, 135 + i * 20) for i in range(5)]
    events += [(15.6, 300), (19.1, 125), (21.8, 170), (24.4, 115), (26.8, 190)]
    path = OUT / "lock-mechanism-original.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        chunk = []
        for i in range(int(rate * DURATION)):
            t = i / rate
            value = 0.016 * math.sin(2 * math.pi * 64 * t) * (0.65 + 0.35 * math.sin(2 * math.pi * 0.17 * t))
            for when, freq in events:
                elapsed = t - when
                if 0 <= elapsed < 0.14:
                    env = math.exp(-elapsed * 42)
                    value += 0.31 * env * math.sin(2 * math.pi * freq * elapsed)
                    value += 0.06 * env * (random.random() * 2 - 1)
            chunk.append(struct.pack("<h", max(-32767, min(32767, int(value * 32767)))))
            if len(chunk) >= 4096:
                out.writeframes(b"".join(chunk))
                chunk.clear()
        if chunk:
            out.writeframes(b"".join(chunk))
    return path


def main() -> None:
    frames = OUT / "lock-frames" / "frame_%04d.png"
    if not frames.with_name("frame_0600.png").is_file():
        raise SystemExit("All 600 Blender frames must be rendered first")
    subtitles = write_ass()
    audio = write_soundtrack()
    output = OUT / "builtwhys-lock-3d-pilot.mp4"
    def ffpath(path: Path) -> str:
        return path.as_posix().replace(":", "\\:")
    video_filter = (
        "minterpolate=fps=30:mi_mode=mci,scale=720:1280:flags=lanczos,"
        f"ass=filename='{ffpath(subtitles)}':fontsdir='{ffpath(FONT_DIR)}'"
    )
    command = [
        "D:/ffmpeg/bin/ffmpeg.exe", "-hide_banner", "-loglevel", "error", "-y",
        "-framerate", "20", "-i", str(frames), "-i", str(audio), "-t", str(DURATION),
        "-vf", video_filter, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(output),
    ]
    subprocess.run(command, check=True)
    print(output)


if __name__ == "__main__":
    main()

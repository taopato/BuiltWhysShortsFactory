"""Finish a locally rendered Blender pilot using the owner's existing narration.

The source task's voice and script were created for BuiltWhys previously. This
does not clone a third-party voice or transmit media to a cloud service.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "storage" / "3d-pilots"
FONT_DIR = ROOT / "resource" / "fonts"
CONFIG = {
    "train": {
        "duration": 29.3,
        "title": "WHEELS THAT STEER",
        "sections": [(0, 6, "NO STEERING WHEEL"), (6, 11, "ONE SHARED AXLE"), (11, 22, "THE HIDDEN TAPER"), (22, 30, "BACK TO CENTER")],
        "tags": ["TAPERED STEEL TREAD", "BOTH WHEELS TURN TOGETHER", "ROLLING RADIUS CHANGES", "GEOMETRY CORRECTS THE DRIFT"],
    },
    "escalator": {
        "duration": 25.6,
        "title": "NOT JUST FOR GRIP",
        "sections": [(0, 9, "NOT JUST FOR GRIP"), (9, 19, "MEET THE COMB"), (19, 26, "THE GAP DISAPPEARS")],
        "tags": ["MOVING STEP + STATIONARY FLOOR", "TEETH ENTER THE GROOVES", "A CONTROLLED HANDOFF"],
    },
    "tape": {
        "duration": 40.45,
        "title": "THE LOOSE HOOK IS THE SECRET",
        "sections": [
            (0, 2, "WHY DOES IT WIGGLE"),
            (2, 5.6, "DO NOT TIGHTEN IT"),
            (5.6, 8.6, "HOOK THE EDGE"),
            (8.6, 13, "PULL IT OUT"),
            (13, 16.1, "PUSH THE WALL"),
            (16.1, 21.05, "IT SLIDES IN"),
            (21.05, 25.9, "SLOTS SET THE TRAVEL"),
            (25.9, 31.75, "ONE TRUE ZERO"),
            (31.75, 35, "FIXED MEANS WRONG"),
            (35, 40.45, "SLACK IS THE FIX"),
        ],
        "tags": [
            "THE WOBBLE IS INTENTIONAL", "A TINY CALIBRATION", "OUTSIDE MEASUREMENT",
            "HOOK MOVES OUTWARD", "INSIDE MEASUREMENT", "HOOK MOVES INWARD",
            "RIVETS + ELONGATED SLOTS", "PULL OR PUSH — SAME ZERO", "THE OFFSET WOULD REMAIN",
            "A MECHANICAL CORRECTION",
        ],
    },
}


def timestamp(value: float) -> str:
    hours = int(value // 3600)
    minutes = int(value % 3600 // 60)
    seconds = value % 60
    return f"{hours}:{minutes:02d}:{seconds:05.2f}"


def parse_srt(path: Path, duration: float):
    text = path.read_text(encoding="utf-8-sig")
    pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})\s*\n([^\n]+)")
    for match in pattern.finditer(text):
        vals = [int(match.group(i)) for i in range(1, 9)]
        start = vals[0] * 3600 + vals[1] * 60 + vals[2] + vals[3] / 1000
        end = vals[4] * 3600 + vals[5] * 60 + vals[6] + vals[7] / 1000
        if start >= duration:
            break
        yield start, min(end, duration), match.group(9).strip()


def ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def write_ass(topic: str, srt: Path) -> Path:
    config = CONFIG[topic]
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 720", "PlayResY: 1280", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Brand,Be Vietnam Pro,19,&H00B7CBDF,&H00FFFFFF,&H00071929,&H00000000,0,0,0,0,100,100,1,0,1,0,0,7,50,50,48,1",
        "Style: Title,Be Vietnam Pro,54,&H00FFFFFF,&H00FFFFFF,&H00071929,&H00000000,-1,0,0,0,100,100,0,0,1,2,1,8,42,42,103,1",
        "Style: Tag,Be Vietnam Pro,20,&H00E6B887,&H00FFFFFF,&H00071929,&H00000000,0,0,0,0,100,100,1,0,1,0,0,8,50,50,175,1",
        "Style: Caption,Be Vietnam Pro,38,&H00FFFFFF,&H00FFFFFF,&H00071929,&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,56,56,365,1",
        "Style: Footer,Be Vietnam Pro,16,&H0099ADC2,&H00FFFFFF,&H00071929,&H00000000,0,0,0,0,100,100,0,0,1,0,0,1,49,49,55,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    end = timestamp(config["duration"])
    lines += [
        f"Dialogue: 0,0:00:00.00,{end},Brand,,0,0,0,,BUILTWHYS  /  HOW IT WORKS",
        f"Dialogue: 0,0:00:00.00,{end},Footer,,0,0,0,,ORIGINAL 3D EXPLAINER  •  PILOT",
    ]
    for (start, stop, title), tag in zip(config["sections"], config["tags"]):
        words = title.split()
        lead = ass_escape(" ".join(words[:-1]))
        accent = ass_escape(words[-1])
        colored_title = f"{lead} {{\\c&H000083FF&}}{accent}" if lead else f"{{\\c&H000083FF&}}{accent}"
        lines.append(f"Dialogue: 1,{timestamp(start)},{timestamp(stop)},Title,,0,0,0,,{colored_title}")
        lines.append(f"Dialogue: 1,{timestamp(start)},{timestamp(stop)},Tag,,0,0,0,,{ass_escape(tag)}")
    for start, stop, caption in parse_srt(srt, config["duration"]):
        wrapped = "\\N".join(ass_escape(part) for part in textwrap.wrap(caption, width=30, break_long_words=False))
        lines.append(f"Dialogue: 2,{timestamp(start)},{timestamp(stop)},Caption,,0,0,0,,{wrapped}")
    result = OUT / f"{topic}.ass"
    result.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", choices=sorted(CONFIG))
    parser.add_argument("--source-task-dir", required=True, type=Path)
    parser.add_argument("--sample", action="store_true")
    args = parser.parse_args()
    topic = args.topic
    duration = 1 if args.sample else CONFIG[topic]["duration"]
    frames = OUT / f"{topic}-{'sample-' if args.sample else ''}frames" / "frame_%04d.png"
    source_audio = args.source_task_dir / "audio.mp3"
    source_srt = args.source_task_dir / "subtitle.srt"
    if not source_audio.is_file() or not source_srt.is_file():
        raise SystemExit("source task must have audio.mp3 and subtitle.srt")
    if not frames.with_name("frame_0001.png").is_file():
        raise SystemExit("Blender frames are missing")
    subs = write_ass(topic, source_srt)
    output = OUT / f"builtwhys-{topic}-3d-{'sample' if args.sample else 'pilot'}.mp4"
    def filter_path(path: Path) -> str:
        return path.as_posix().replace(":", "\\:")

    video_filter = "minterpolate=fps=30:mi_mode=mci,scale=720:1280:flags=lanczos," + (
        f"ass=filename='{filter_path(subs)}':fontsdir='{filter_path(FONT_DIR)}'"
    )
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "20",
        "-i", str(frames), "-i", str(source_audio), "-t", str(duration),
        "-vf", video_filter, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-af", "afade=t=out:st=" + str(duration - 0.15) + ":d=0.15",
        "-movflags", "+faststart", str(output),
    ]
    subprocess.run(command, check=True)
    print(output)


if __name__ == "__main__":
    main()

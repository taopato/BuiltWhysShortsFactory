"""Finish the second lock pilot; review-only, no server/publisher integration."""

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
DURATION = 24
BEATS = [
    (0.00, 2.75, "THE HIDDEN TEST", "A door key must pass five tiny tests."),
    (2.75, 5.15, "WRONG KEY", "One bad cut leaves the plug blocked."),
    (5.15, 6.90, "MISALIGNED PINS", "A driver pin crosses the shear line."),
    (6.90, 10.25, "RIGHT KEY", "Its cuts raise each pin by a different amount."),
    (10.25, 14.00, "FIVE PIN PAIRS", "Watch the pins move, one after another."),
    (14.00, 17.40, "ONE CLEAR LINE", "Their junctions meet the shear line."),
    (17.40, 20.75, "THE PLUG TURNS", "Now nothing blocks its rotation."),
    (20.75, 24.00, "BOLT RETRACTS", "The turning cam draws the bolt inward."),
]


def stamp(t: float) -> str:
    return f"0:00:{t:05.2f}"


def write_titles() -> Path:
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 720", "PlayResY: 1280", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Brand,Be Vietnam Pro,18,&H00FFFFFF,&H00FFFFFF,&H00070D19,&H00000000,0,0,0,0,100,100,1,0,1,1,0,7,54,54,54,1",
        "Style: Eyebrow,Be Vietnam Pro,20,&H003D88FF,&H00FFFFFF,&H00070D19,&H00000000,-1,0,0,0,100,100,1,0,1,1,0,7,55,55,158,1",
        "Style: Head,Be Vietnam Pro,51,&H00FFFFFF,&H00FFFFFF,&H00070D19,&H00000000,-1,0,0,0,100,100,0,0,1,2,1,7,55,55,201,1",
        "Style: Caption,Be Vietnam Pro,34,&H00FFFFFF,&H00FFFFFF,&H00070D19,&H9A071321,-1,0,0,0,100,100,0,0,3,1,0,2,55,55,235,1",
        "Style: Footer,Be Vietnam Pro,15,&H00AAB5C8,&H00FFFFFF,&H00070D19,&H00000000,0,0,0,0,100,100,0,0,1,1,0,1,54,54,52,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        "Dialogue: 0,0:00:00.00,0:00:24.00,Brand,,0,0,0,,BUILTWHYS  /  ORIGINAL 3D",
        "Dialogue: 0,0:00:00.00,0:00:24.00,Footer,,0,0,0,,VISUAL PROTOTYPE  •  NOT PUBLISHED",
    ]
    for index, (start, end, title, caption) in enumerate(BEATS, 1):
        lines.append(f"Dialogue: 1,{stamp(start)},{stamp(end)},Eyebrow,,0,0,0,,{{\\fad(120,120)}}•  HOW A LOCK WORKS  /  {index:02d}")
        lines.append(f"Dialogue: 2,{stamp(start)},{stamp(end)},Head,,0,0,0,,{{\\fad(130,130)}}{title}")
        lines.append(f"Dialogue: 3,{stamp(start)},{stamp(end)},Caption,,0,0,0,,{{\\fad(140,140)}}{caption}")
    out = OUT / "lock-realistic.ass"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def sound() -> Path:
    rate = 24_000
    random.seed(31)
    # Individual contact clicks deliberately coincide with five pin actions.
    events = [(0.12,180),(2.78,145),(5.20,110),(7.0,175)]
    events += [(10.5+i*0.66,150+i*17) for i in range(5)]
    events += [(14.15,260),(17.55,145),(19.40,210),(20.85,120),(22.65,195)]
    outpath = OUT / "lock-realistic-original-sfx.wav"
    with wave.open(str(outpath), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        block = []
        for i in range(rate * DURATION):
            t = i / rate
            value = 0.014 * math.sin(2*math.pi*57*t) * (0.75+0.25*math.sin(2*math.pi*.23*t))
            for when, freq in events:
                delta = t-when
                if 0 <= delta < 0.17:
                    env = math.exp(-delta*40)
                    value += 0.31*env*math.sin(2*math.pi*freq*delta)
                    value += 0.055*env*(random.random()*2-1)
            block.append(struct.pack("<h",max(-32767,min(32767,int(value*32767)))))
            if len(block) == 4096:
                out.writeframes(b"".join(block))
                block.clear()
        if block:
            out.writeframes(b"".join(block))
    return outpath


def main() -> None:
    sequence = OUT / "lock-realistic-frames" / "frame_%04d.png"
    if not sequence.with_name("frame_0480.png").is_file():
        raise SystemExit("The 480 Blender frames must be complete first")
    subs = write_titles()
    audio = sound()
    output = OUT / "builtwhys-lock-realistic-pilot.mp4"
    def ffpath(p: Path) -> str:
        return p.as_posix().replace(":", "\\:")
    vf = "minterpolate=fps=30:mi_mode=mci,scale=720:1280:flags=lanczos," + (
        f"ass=filename='{ffpath(subs)}':fontsdir='{ffpath(FONT_DIR)}'"
    )
    subprocess.run([
        "D:/ffmpeg/bin/ffmpeg.exe","-hide_banner","-loglevel","error","-y",
        "-framerate","20","-i",str(sequence),"-i",str(audio),"-t",str(DURATION),
        "-vf",vf,"-c:v","libx264","-preset","medium","-crf","19",
        "-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-movflags","+faststart",str(output),
    ],check=True)
    print(output)


if __name__ == "__main__":
    main()

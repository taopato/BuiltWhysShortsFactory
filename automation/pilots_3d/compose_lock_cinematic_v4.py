"""Assemble the review-only lock pilot from local renders and narration.

No channel, API, queue, or production state is accessed by this script.
"""

from __future__ import annotations

import asyncio
import math
import random
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

sys.path.insert(0, "D:/CreatorLab/Tools/pilot_py")
import edge_tts

ROOT = Path(__file__).resolve().parents[2]
OUT = Path("D:/CreatorLab/ShortsFactory/pilots/lock-v4")
FFMPEG = Path("D:/ffmpeg/bin/ffmpeg.exe")
FFPROBE = Path("D:/ffmpeg/bin/ffprobe.exe")
FPS = 24
SECONDS = 36
VOICE = "en-US-AndrewMultilingualNeural"

BEATS = [
    (0.20, "Your key doesn't push a lock open."),
    (3.15, "It lines up five tiny hidden pins."),
    (6.75, "Watch as the key slides in."),
    (10.4, "Each cut lifts one pin to a different height."),
    (15.1, "Every seam must meet this shear line."),
    (19.25, "Only then can the inner cylinder turn."),
    (23.2, "That turn pulls the bolt back."),
    (28.7, "And the door opens."),
    (32.0, "Five tiny pins. One precise key."),
]


def run(*args: str) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def duration(path: Path) -> float:
    return float(run(str(FFPROBE), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)))


async def narrate() -> list[tuple[float, str, Path, float]]:
    audio_dir = OUT / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    result=[]
    for i,(start,words) in enumerate(BEATS):
        audio_file=audio_dir / ("line_08_v2.mp3" if i==8 else f"line_{i:02d}.mp3")
        if not audio_file.exists() or audio_file.stat().st_size<1000:
            for attempt in range(5):
                try:
                    await edge_tts.Communicate(words, VOICE, rate="+8%").save(str(audio_file))
                    if audio_file.stat().st_size<1000:
                        raise RuntimeError("Empty voice response")
                    break
                except Exception as exc:
                    audio_file.unlink(missing_ok=True)
                    if attempt==4: raise
                    print(f"Voice retry {i}/{attempt+1}: {exc}",flush=True)
                    await asyncio.sleep(1.5*(attempt+1))
        length=duration(audio_file)
        result.append((start,words,audio_file,length))
        print(f"VOICE {i:02d} {start:.2f}+{length:.2f}s: {words}",flush=True)
    return result


def ass_time(seconds: float) -> str:
    centis=round(seconds*100)
    return f"{centis//360000}:{centis//6000%60:02d}:{centis//100%60:02d}.{centis%100:02d}"


def captions(lines: list[tuple[float,str,Path,float]]) -> Path:
    output=OUT / "captions.ass"
    header="""[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00301A0B,&H96000000,-1,0,0,0,100,100,0,0,1,3,1,2,72,72,235,1
Style: Hook,Arial,54,&H00FFFFFF,&H00FFFFFF,&H00171921,&H90000000,-1,0,0,0,100,100,0,0,1,3,1,8,65,65,185,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events=["Dialogue: 0,0:00:00.00,0:00:03.10,Hook,,0,0,0,,A KEY DOESN'T PUSH\\nTHE LOCK OPEN"]
    for start,words,_,length in lines:
        end=min(SECONDS-.12,start+length+.15)
        if end<=start:
            continue
        wrapped=textwrap.wrap(words,width=22,break_long_words=False,break_on_hyphens=False)
        words=r"\N".join(wrapped).replace("{","(").replace("}",")")
        events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Main,,0,0,0,,{words}")
    output.write_text(header+"\n".join(events)+"\n",encoding="utf-8")
    return output


def make_foley() -> Path:
    output=OUT/"audio"/"foley.wav"
    sample_rate=48000
    length=SECONDS*sample_rate
    rng=random.Random(37)
    ticks=(.15,3.1,9.8,13.0,15.8,18.0,21.0,23.0,27.4,30.0,34.0)
    with wave.open(str(output),"wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate)
        chunk=[]
        for i in range(length):
            t=i/sample_rate
            pad=.018*math.sin(math.tau*65*t)+.012*math.sin(math.tau*98.3*t)
            hiss=.006*(rng.random()*2-1)
            tick=0.0
            for hit in ticks:
                dt=t-hit
                if 0<=dt<.12:
                    tick+=.13*math.exp(-36*dt)*math.sin(math.tau*1200*dt)
            value=max(-1,min(1,pad+hiss+tick))
            chunk.append(int(value*32767).to_bytes(2,"little",signed=True))
            if len(chunk)>=8192:
                wav.writeframes(b"".join(chunk)); chunk=[]
        if chunk: wav.writeframes(b"".join(chunk))
    return output


def assemble(lines: list[tuple[float,str,Path,float]], subtitle: Path, foley: Path) -> Path:
    frames=OUT/"frames"
    if len(list(frames.glob("frame_*.png"))) != FPS*SECONDS:
        raise RuntimeError("All 864 rendered frames are required before assembly")
    output=OUT/"lock-cinematic-pilot-v4.mp4"
    args=[str(FFMPEG),"-hide_banner","-y","-framerate",str(FPS),"-i",str(frames/"frame_%04d.png")]
    for _,_,path,_ in lines: args.extend(("-i",str(path)))
    args.extend(("-i",str(foley)))
    filters=[]
    audio_inputs=[]
    for i,(start,_,_,_) in enumerate(lines,1):
        delay=round(start*1000)
        filters.append(f"[{i}:a]aresample=48000,adelay={delay}|{delay},volume=1.35[a{i}]")
        audio_inputs.append(f"[a{i}]")
    foley_index=len(lines)+1
    filters.append(f"[{foley_index}:a]aresample=48000,volume=0.65[foley]")
    filters.append("".join(audio_inputs)+"[foley]amix=inputs="+str(len(audio_inputs)+1)+":duration=longest:normalize=0,alimiter=limit=0.94[aout]")
    sub_path=subtitle.as_posix().replace(":", "\\:")
    args.extend(("-filter_complex",";".join(filters),"-vf",f"ass='{sub_path}'","-map","0:v","-map","[aout]","-c:v","libx264","-preset","medium","-crf","19","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-t",str(SECONDS),"-movflags","+faststart",str(output)))
    subprocess.run(args,check=True)
    return output


async def main() -> None:
    lines=await narrate()
    for index,(start,_,_,length) in enumerate(lines[:-1]):
        next_start=lines[index+1][0]
        if start+length>next_start+.2:
            print(f"WARNING narration overlap at beat {index}: {start+length:.2f} > {next_start:.2f}")
    subtitle=captions(lines)
    foley=make_foley()
    print("CAPTIONS",subtitle)
    if "--compose" in sys.argv:
        print("OUTPUT",assemble(lines,subtitle,foley))


if __name__=="__main__":
    asyncio.run(main())

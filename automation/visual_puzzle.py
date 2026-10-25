from __future__ import annotations

import hashlib
import json
import math
import struct
import subprocess
import wave
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT, FPS, DURATION = 540, 960, 15, 36
BG, PANEL, WHITE, MUTED = "#080b10", "#141a24", "#f5f3ea", "#8f98a8"
ACCENTS = ("#58d89c", "#ffbf5b", "#6ca8ff")


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        ROOT / "resource" / "fonts" / "BeVietnamPro-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _center(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int, fill: str = WHITE) -> None:
    font = _font(size)
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (box[2] - box[0]) / 2, xy[1] - (box[3] - box[1]) / 2), text, font=font, fill=fill)


def _base_frame(progress: float, answer: int, reveal: bool) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, 82, 82), 14, outline=WHITE, width=3)
    _center(draw, (53, 53), "BW", 18)
    _center(draw, (270, 112), "?", 58)
    draw.rounded_rectangle((35, 160, 505, 800), 28, fill=PANEL, outline="#283140", width=2)
    for i, x in enumerate((125, 270, 415)):
        color = "#4cdb92" if reveal and i == answer else ACCENTS[i]
        draw.ellipse((x - 28, 830, x + 28, 886), fill=color)
        _center(draw, (x, 858), "ABC"[i], 22, BG)
    draw.rounded_rectangle((35, 916, 505, 926), 5, fill="#222936")
    draw.rounded_rectangle((35, 916, 35 + int(470 * progress), 926), 5, fill="#4cdb92")
    return image, draw


def _countdown(draw: ImageDraw.ImageDraw, second: float) -> None:
    if 7 <= second < 13:
        value = max(1, 3 - int((second - 7) / 2))
        draw.ellipse((205, 380, 335, 510), fill="#080b10dd", outline=WHITE, width=4)
        _center(draw, (270, 445), str(value), 62)


def _gear_scene(draw: ImageDraw.ImageDraw, t: float, reveal: bool) -> int:
    centers = [(125, 430), (270, 430), (415, 430)]
    counts = (3, 4, 5)
    for column, (cx, cy) in enumerate(centers):
        for index in range(counts[column]):
            y = cy + (index - counts[column] / 2) * 72
            radius = 39
            draw.ellipse((cx - radius, y - radius, cx + radius, y + radius), outline=ACCENTS[column], width=5)
            angle = (t * (1 if index % 2 == 0 else -1) * 3.0) + index
            draw.line((cx, y, cx + math.cos(angle) * 29, y + math.sin(angle) * 29), fill=WHITE, width=4)
    if reveal:
        draw.ellipse((230, 220, 310, 300), outline="#4cdb92", width=8)
    return 1


def _tank_scene(draw: ImageDraw.ImageDraw, t: float, reveal: bool) -> int:
    rates = (0.72, 1.0, 0.55)
    for i, x in enumerate((75, 220, 365)):
        draw.rounded_rectangle((x, 285, x + 100, 625), 16, outline=ACCENTS[i], width=5)
        drained = min(1.0, max(0.0, (t - 13) / 15) * rates[i])
        top = int(315 + 285 * drained)
        draw.rectangle((x + 8, top, x + 92, 610), fill="#3177c9")
        draw.line((x + 50, 625, x + 50, 690), fill=WHITE, width=6)
    return 1


def _ball_scene(draw: ImageDraw.ImageDraw, t: float, reveal: bool) -> int:
    speeds = (0.72, 0.58, 1.0)
    for i, x in enumerate((125, 270, 415)):
        draw.line((x, 250, x, 675), fill="#3a4352", width=9)
        p = min(1.0, max(0.0, (t - 13) / 14) * speeds[i])
        wobble = math.sin(p * math.pi * (i + 2)) * (20 + i * 4)
        y = 260 + int(400 * p)
        draw.ellipse((x - 25 + wobble, y - 25, x + 25 + wobble, y + 25), fill=ACCENTS[i], outline=WHITE, width=3)
    return 2


def _domino_scene(draw: ImageDraw.ImageDraw, t: float, reveal: bool) -> int:
    speeds = (0.78, 1.0, 0.63)
    for row, y in enumerate((315, 455, 595)):
        progress = min(1.0, max(0.0, (t - 13) / 14) * speeds[row])
        for index in range(9):
            x = 75 + index * 48
            fallen = index / 8 <= progress
            if fallen:
                draw.line((x - 15, y + 18, x + 18, y - 12), fill=ACCENTS[row], width=10)
            else:
                draw.rounded_rectangle((x - 7, y - 26, x + 7, y + 26), 4, fill=WHITE)
    return 1


def _lever_scene(draw: ImageDraw.ImageDraw, t: float, reveal: bool) -> int:
    pivots = (0.33, 0.5, 0.67)
    for i, y in enumerate((315, 465, 615)):
        x1, x2 = 75, 465
        px = int(x1 + (x2 - x1) * pivots[i])
        tilt = min(0.16, max(0.0, (t - 13) / 14) * (0.16 if i == 0 else 0.08))
        draw.line((x1, y + tilt * 100, x2, y - tilt * 100), fill=ACCENTS[i], width=13)
        draw.polygon([(px, y + 8), (px - 26, y + 62), (px + 26, y + 62)], fill=WHITE)
        draw.rectangle((x2 - 35, y - 55, x2 + 5, y - 15), fill="#626b7b")
    return 0


def _scene_kind(topic: str) -> str:
    value = topic.lower()
    if "gear" in value or "wheel" in value or "pulley" in value:
        return "gear"
    if "tank" in value or "pipe" in value or "cup" in value:
        return "tank"
    if "ball" in value or "marble" in value or "route" in value:
        return "ball"
    if "domino" in value or "stack" in value:
        return "domino"
    return "lever"


def _audio(path: Path) -> None:
    rate, frames = 44100, DURATION * 44100
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, rate, frames, "NONE", "not compressed"))
        for index in range(frames):
            second = index / rate
            value = 0.012 * math.sin(2 * math.pi * 110 * second)
            for moment, frequency, amplitude in ((8, 550, .18), (10, 650, .18), (12, 760, .18), (28, 980, .22)):
                distance = second - moment
                if 0 <= distance < .22:
                    value += amplitude * math.sin(2 * math.pi * frequency * distance) * (1 - distance / .22)
            output.writeframesraw(struct.pack("<h", int(max(-1, min(1, value)) * 32767)))


def render(job: dict[str, Any], pilot: Path) -> tuple[Path, Path, Path]:
    pilot.mkdir(parents=True, exist_ok=True)
    assets = pilot / "assets-original"
    assets.mkdir(exist_ok=True)
    output = ROOT / "storage" / "renders" / f"{job['id']}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    audio = pilot / "sound-design.wav"
    _audio(audio)
    kind = _scene_kind(str(job["topic"]))
    scene = {"gear": _gear_scene, "tank": _tank_scene, "ball": _ball_scene,
             "domino": _domino_scene, "lever": _lever_scene}[kind]
    answer = {"gear": 1, "tank": 1, "ball": 2, "domino": 1, "lever": 0}[kind]
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-i", str(audio), "-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart", str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    snapshots: list[Path] = []
    try:
        for frame_no in range(DURATION * FPS):
            second = frame_no / FPS
            reveal = second >= 28
            image, draw = _base_frame(frame_no / (DURATION * FPS - 1), answer, reveal)
            scene(draw, second, reveal)
            _countdown(draw, second)
            if reveal:
                _center(draw, (270, 735), "✓", 72, "#4cdb92")
            if frame_no in {0, 60, 105, 150, 225, 300, 420, 525}:
                snapshot = assets / f"scene-{len(snapshots) + 1:02d}.png"
                image.save(snapshot, optimize=True)
                snapshots.append(snapshot)
            assert process.stdin is not None
            process.stdin.write(image.tobytes())
    finally:
        if process.stdin:
            process.stdin.close()
    if process.wait() != 0 or not output.is_file():
        raise RuntimeError("visual puzzle ffmpeg render failed")
    sources = [
        {"title": "Simple machines", "publisher": "OpenStax Physics",
         "url": "https://openstax.org/books/physics/pages/9-3-simple-machines"},
        {"title": "Simple machine", "publisher": "Encyclopaedia Britannica",
         "url": "https://www.britannica.com/technology/simple-machine"},
    ]
    manifest = pilot / "manifest.json"
    manifest.write_text(json.dumps({
        "job_id": job["id"], "ai_disclosure_required": False,
        "generation": "Original deterministic Pillow animation rendered locally",
        "fact_sources": sources,
        "assets": [{
            "type": "procedural_diagram", "source_url": f"local://{path.relative_to(ROOT).as_posix()}",
            "license": "BuiltWhys original procedural artwork", "commercial_use": True,
        } for path in snapshots],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    thumbnail = assets / "scene-01.png"
    return output, manifest, thumbnail


def storyboard(topic: str) -> str:
    kind = _scene_kind(topic)
    scripts = {
        "gear": (
            "Three separate gear trains begin with their top wheel turning at the same instant. "
            "Each column contains a different number of meshing wheels, so every contact reverses rotation. "
            "The viewer follows the spokes and predicts the final wheel direction in A, B or C. "
            "After the countdown, the middle mechanism is isolated and its clockwise output receives a green check."
        ),
        "tank": (
            "Three transparent tanks start at an equal water level, but their outlets drain at different rates. "
            "Blue fill visibly falls while the pipes remain open beneath A, B and C. "
            "The challenge is to spot which vessel reaches empty first from the changing levels alone. "
            "At the reveal, tank B finishes before its neighbors and is marked with a green check."
        ),
        "ball": (
            "Three colored balls are released together onto separate vertical routes. "
            "Their paths introduce different sideways motion and travel progress, making the apparent leader change. "
            "The viewer tracks A, B and C during one uninterrupted race toward the bottom line. "
            "Route C completes the journey first; its ball and label are highlighted when the answer is revealed."
        ),
        "domino": (
            "Three rows of upright dominoes receive the same starting push. "
            "Spacing and propagation speed differ across the upper, middle and lower chains. "
            "Tiles tip one after another while the viewer predicts which reaction crosses its final position first. "
            "The central B row completes the chain ahead of A and C, then the winning row receives the answer marker."
        ),
        "lever": (
            "Three beams carry matching loads but place their triangular fulcrums at different distances. "
            "The unequal force arms cause the bars to tilt at visibly different rates after release. "
            "The viewer compares leverage in A, B and C before choosing the mechanism that moves the load most effectively. "
            "Lever A demonstrates the winning geometry and gains the green result highlight."
        ),
    }
    return scripts[kind]


def candidate_hash(topic: str) -> str:
    return hashlib.sha256(topic.encode("utf-8")).hexdigest()[:12]

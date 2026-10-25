from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT, FPS = 720, 1280, 24
CHUNK_SECONDS, CHUNKS = 5, 4


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path(__file__).resolve().parents[1] / "resource" / "fonts" / "BeVietnamPro-Bold.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ):
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


TITLE_FONT = _font(40)
LABEL_FONT = _font(25)
SMALL_FONT = _font(18)


def _ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def _base(title: str, phase: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#071019")
    draw = ImageDraw.Draw(image)
    for x in range(0, WIDTH, 48):
        draw.line((x, 0, x, HEIGHT), fill="#10202c", width=1)
    for y in range(0, HEIGHT, 48):
        draw.line((0, y, WIDTH, y), fill="#10202c", width=1)
    draw.rounded_rectangle((35, 38, WIDTH - 35, 154), 22, fill="#0e1c27", outline="#2b4557", width=2)
    draw.text((58, 60), title[:28].upper(), font=TITLE_FONT, fill="#f6f2e8")
    draw.text((58, 117), phase.upper(), font=SMALL_FONT, fill="#63dda4")
    draw.text((42, HEIGHT - 72), "BUILTWHYS  /  ORIGINAL MECHANISM", font=SMALL_FONT, fill="#718391")
    return image, draw


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, width: int = 8) -> None:
    draw.line((*start, *end), fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 18
    left = (end[0] - int(size * math.cos(angle - 0.65)), end[1] - int(size * math.sin(angle - 0.65)))
    right = (end[0] - int(size * math.cos(angle + 0.65)), end[1] - int(size * math.sin(angle + 0.65)))
    draw.polygon([end, left, right], fill=color)


def _bottle_frame(seconds: float) -> Image.Image:
    phases = ("THE LOAD", "FLAT BASE", "PRESSURE SPREADS", "STABLE RESULT")
    phase = min(3, int(seconds // 5))
    image, draw = _base("Why bottles have feet", phases[phase])
    pressure = 0.1 + 0.9 * _ease((seconds % 5) / 5)
    cx, top, bottom = 360, 270, 965
    draw.rounded_rectangle((225, top, 495, bottom), 92, fill="#16334b", outline="#8ad9ff", width=7)
    draw.rectangle((235, 390, 485, bottom - 28), fill="#2e91b9")
    draw.line((235, 390, 485, 390), fill="#c3f3ff", width=5)
    if phase == 1:
        bulge = int(55 * pressure)
        draw.arc((225, bottom - 65, 495, bottom + bulge), 0, 180, fill="#ff6d6d", width=13)
        draw.text((238, 1040), "ONE WEAK SURFACE", font=LABEL_FONT, fill="#ff8b82")
    else:
        points = []
        for index in range(11):
            x = 235 + index * 25
            y = bottom - 12 - int((20 + 38 * pressure) * abs(math.sin(index * math.pi / 5)))
            points.append((x, y))
        draw.line(points, fill="#63dda4", width=14, joint="curve")
        draw.text((214, 1040), "LOAD SHARED BY FIVE FEET", font=LABEL_FONT, fill="#63dda4")
    if phase in {0, 2}:
        for x in (270, 315, 360, 405, 450):
            _arrow(draw, (x, 500), (x, 780 + int(80 * pressure)), "#ffbf5a", 7)
    if phase == 3:
        draw.line((185, bottom + 5, 535, bottom + 5), fill="#f6f2e8", width=8)
        draw.text((280, 1100), "NO WOBBLE", font=LABEL_FONT, fill="#f6f2e8")
    return image


def _bridge_frame(seconds: float) -> Image.Image:
    phases = ("TWO DECKS", "HEAT EXPANDS", "THE GAP MOVES", "TRAFFIC STAYS LEVEL")
    phase = min(3, int(seconds // 5))
    image, draw = _base("Bridge expansion joint", phases[phase])
    cycle = 0.5 + 0.5 * math.sin(seconds * 1.25)
    shift = int((12 if phase == 0 else 45) * cycle)
    left_end, right_start = 335 + shift, 385 - shift
    draw.rounded_rectangle((45, 555, left_end, 760), 20, fill="#586776", outline="#d8e0e6", width=5)
    draw.rounded_rectangle((right_start, 555, 675, 760), 20, fill="#586776", outline="#d8e0e6", width=5)
    for x in range(left_end - 55, right_start + 56, 25):
        draw.line((x, 570, x - 20, 745), fill="#ffbf5a", width=8)
    draw.line((40, 775, 680, 775), fill="#2b4557", width=12)
    if phase in {1, 2}:
        _arrow(draw, (210, 455), (left_end - 8, 455), "#ff6d6d")
        _arrow(draw, (510, 455), (right_start + 8, 455), "#ff6d6d")
        draw.text((242, 855), "METAL GETS LONGER", font=LABEL_FONT, fill="#ff8b82")
    else:
        draw.text((252, 855), "CONTROLLED MOVEMENT", font=LABEL_FONT, fill="#63dda4")
    car_x = int(55 + (seconds / 20) * 570)
    draw.rounded_rectangle((car_x, 470, car_x + 105, 535), 18, fill="#63dda4")
    draw.ellipse((car_x + 14, 515, car_x + 40, 541), fill="#09131c")
    draw.ellipse((car_x + 68, 515, car_x + 94, 541), fill="#09131c")
    return image


def _seatbelt_frame(seconds: float) -> Image.Image:
    phases = ("NORMAL PULL", "SUDDEN JERK", "PAWL ENGAGES", "BELT LOCKED")
    phase = min(3, int(seconds // 5))
    image, draw = _base("How a seat belt locks", phases[phase])
    cx, cy, radius = 360, 650, 178
    speed = 1.2 if phase == 0 else (7.5 if phase == 1 else 0.15)
    angle = seconds * speed
    draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill="#142a3a", outline="#8ad9ff", width=8)
    teeth = []
    for i in range(24):
        a = angle + i * math.tau / 24
        outer = radius + (14 if i % 2 == 0 else 0)
        teeth.append((cx + int(math.cos(a) * outer), cy + int(math.sin(a) * outer)))
    draw.polygon(teeth, outline="#d8e0e6")
    draw.ellipse((cx-70, cy-70, cx+70, cy+70), fill="#687b8b")
    draw.line((cx + radius, cy, 665, cy), fill="#f6f2e8", width=34)
    pawl_y = 420 if phase < 2 else 486
    draw.polygon([(270, pawl_y), (335, pawl_y + 48), (300, pawl_y + 112), (245, pawl_y + 38)], fill="#ffbf5a")
    if phase >= 2:
        draw.ellipse((285, 515, 325, 555), fill="#ff6d6d")
        draw.text((238, 935), "TEETH STOP THE SPOOL", font=LABEL_FONT, fill="#63dda4")
    else:
        _arrow(draw, (525, 875), (635, 875), "#ffbf5a")
        draw.text((180, 935), "BELT MOVES FREELY", font=LABEL_FONT, fill="#f6f2e8")
    return image


def _generic_frame(seconds: float) -> Image.Image:
    image, draw = _base("Hidden design mechanism", ("LOAD", "RESPONSE", "CONTROL", "RESULT")[min(3, int(seconds // 5))])
    phase = seconds / 20
    left = 100 + int(70 * math.sin(seconds))
    draw.rounded_rectangle((left, 480, left + 220, 800), 35, fill="#27465b", outline="#8ad9ff", width=7)
    draw.rounded_rectangle((430, 480, 620, 800), 35, fill="#586776", outline="#d8e0e6", width=7)
    _arrow(draw, (left + 230, 640), (415, 640), "#ffbf5a")
    draw.text((172, 920), "MOTION BECOMES CONTROL", font=LABEL_FONT, fill="#63dda4")
    draw.arc((120, 320, 600, 1080), int(phase * 200), int(phase * 200 + 100), fill="#63dda4", width=6)
    return image


def renderer_for(topic: str) -> tuple[str, Callable[[float], Image.Image]]:
    lowered = topic.lower()
    if any(word in lowered for word in ("bottle", "petaloid", "soda bottle", "şişe")):
        return "bottle-base-pressure", _bottle_frame
    if any(word in lowered for word in ("bridge", "expansion joint", "köprü")):
        return "bridge-expansion-joint", _bridge_frame
    if any(word in lowered for word in ("seat belt", "seatbelt", "emniyet kemeri")):
        return "seatbelt-retractor-lock", _seatbelt_frame
    return "generic-load-response", _generic_frame


def install_hybrid_mechanism(pilot: Path, topic: str) -> list[Path]:
    """Replace the middle stock section with four original 2D animation clips."""
    assets = pilot / "assets-v3"
    assets.mkdir(parents=True, exist_ok=True)
    final_pexels = assets / "scene-06-pexels.mp4"
    final_meta = assets / "scene-06-pexels.json"
    if not final_pexels.is_file():
        raise RuntimeError("hybrid pack requires the sixth Pexels clip as its real-footage ending")
    final_pexels.replace(assets / "scene-07-pexels.mp4")
    if final_meta.is_file():
        final_meta.replace(assets / "scene-07-pexels.json")
    for index in range(3, 7):
        for old in assets.glob(f"scene-{index:02d}-*"):
            old.unlink(missing_ok=True)
    for old in assets.glob("scene-0[78]-diagram.*"):
        old.unlink(missing_ok=True)

    template, render_frame = renderer_for(topic)
    outputs: list[Path] = []
    for chunk in range(CHUNKS):
        output = assets / f"scene-{chunk + 3:02d}-mechanism.mp4"
        process = subprocess.Popen(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "rawvideo",
                "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS),
                "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                "-y", str(output),
            ],
            stdin=subprocess.PIPE,
        )
        assert process.stdin is not None
        try:
            for frame_index in range(CHUNK_SECONDS * FPS):
                seconds = chunk * CHUNK_SECONDS + frame_index / FPS
                process.stdin.write(render_frame(seconds).tobytes())
        finally:
            process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError(f"procedural mechanism render failed for chunk {chunk + 1}")
        outputs.append(output)

    manifest_path = pilot / "manifest-v3.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    retained = [
        asset for asset in manifest.get("assets", [])
        if Path(str(asset.get("local_file") or asset.get("source_url") or "")).name.startswith(("scene-01-", "scene-02-", "scene-06-"))
    ]
    for asset in retained:
        if Path(str(asset.get("local_file") or "")).name.startswith("scene-06-"):
            asset["local_file"] = str(asset["local_file"]).replace("scene-06-", "scene-07-")
    project_root = Path(__file__).resolve().parents[1]
    retained.extend({
        "type": "procedural_animation",
        "source_url": f"local://{path.relative_to(project_root).as_posix()}",
        "local_file": path.relative_to(project_root).as_posix(),
        "license": "Project-generated original 2D mechanism animation",
        "commercial_use": True,
        "template": template,
    } for path in outputs)
    manifest["assets"] = retained
    manifest["visual_strategy"] = "two real Pexels hook clips, twenty seconds of original procedural mechanism animation, then real Pexels footage"
    manifest["hybrid_template"] = template
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pilot / "hybrid_plan.json").write_text(json.dumps({
        "template": template,
        "opening": "two Pexels clips",
        "mechanism_seconds": 20,
        "ending": "one Pexels clip",
        "generation": "local Pillow + FFmpeg; no paid image or video API",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return outputs

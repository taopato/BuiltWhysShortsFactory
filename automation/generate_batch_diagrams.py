from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
W, H = 1080, 1920
BG_TOP = (7, 15, 28)
BG_BOTTOM = (17, 36, 55)
CYAN = (74, 214, 255)
BLUE = (53, 116, 255)
AMBER = (255, 190, 58)
RED = (255, 92, 92)
STEEL = (170, 190, 205)
WHITE = (238, 247, 255)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(image)
    for y in range(H):
        t = y / (H - 1)
        color = tuple(int(a * (1 - t) + b * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        draw.line((0, y, W, y), fill=color)
    for x in range(80, W, 120):
        draw.line((x, 0, x, H), fill=(20, 46, 65), width=1)
    for y in range(80, H, 120):
        draw.line((0, y, W, y), fill=(20, 46, 65), width=1)
    return image, draw


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color=CYAN, width=18) -> None:
    draw.line((*start, *end), fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = width * 2.2
    left = (end[0] - size * math.cos(angle - 0.55), end[1] - size * math.sin(angle - 0.55))
    right = (end[0] - size * math.cos(angle + 0.55), end[1] - size * math.sin(angle + 0.55))
    draw.polygon([end, left, right], fill=color)


def save(name: str, image: Image.Image) -> None:
    path = ROOT / "automation" / "pilots" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def train_circles() -> None:
    im, d = canvas()
    d.line((160, 1340, 920, 1340), fill=STEEL, width=36)
    d.line((250, 850, 830, 850), fill=STEEL, width=55)
    d.ellipse((150, 650, 500, 1100), outline=WHITE, width=45)
    d.ellipse((610, 720, 890, 1050), outline=WHITE, width=45)
    d.ellipse((205, 705, 445, 1045), outline=AMBER, width=14)
    d.ellipse((655, 765, 845, 1015), outline=CYAN, width=14)
    arrow(d, (280, 565), (430, 565), AMBER)
    arrow(d, (785, 580), (670, 580), CYAN)
    arrow(d, (540, 1190), (540, 1040), WHITE)
    save("002-train-wheels/assets/scene-02-rolling-circles.png", im)


def train_curve() -> None:
    im, d = canvas()
    for offset in (-130, 130):
        points = []
        for y in range(200, 1650, 20):
            x = 520 + offset + int(210 * math.sin((y - 200) / 1450 * 1.25))
            points.append((x, y))
        d.line(points, fill=STEEL, width=34)
    for y in range(360, 1540, 170):
        center = 520 + int(210 * math.sin((y - 200) / 1450 * 1.25))
        d.line((center - 220, y, center + 220, y), fill=(85, 105, 120), width=24)
    d.line((335, 850, 790, 930), fill=WHITE, width=48)
    d.ellipse((300, 760, 430, 965), fill=(40, 54, 67), outline=CYAN, width=18)
    d.ellipse((700, 830, 830, 1035), fill=(40, 54, 67), outline=AMBER, width=18)
    arrow(d, (500, 640), (610, 720), CYAN)
    save("002-train-wheels/assets/scene-03-curve.png", im)


def escalator_comb() -> None:
    im, d = canvas()
    for x in range(80, 1030, 55):
        d.rounded_rectangle((x, 770, x + 28, 1530), 10, fill=STEEL)
    d.rectangle((0, 560, W, 780), fill=(205, 151, 26))
    for x in range(68, 1040, 55):
        d.polygon([(x, 780), (x + 34, 780), (x + 25, 1060), (x + 8, 1060)], fill=AMBER)
    arrow(d, (160, 440), (900, 440), CYAN, 20)
    save("003-escalator-grooves/assets/scene-02-comb-mesh.png", im)


def escalator_handoff() -> None:
    im, d = canvas()
    steps = [(80, 1280), (250, 1110), (420, 940), (590, 840), (760, 840)]
    for x, y in steps:
        d.line((x, y, x + 230, y), fill=STEEL, width=90)
        d.line((x + 230, y, x + 230, y + 170), fill=(95, 120, 137), width=60)
    d.rectangle((690, 650, W, 810), fill=(60, 75, 88))
    d.polygon([(680, 810), (900, 810), (845, 930), (630, 930)], fill=AMBER)
    arrow(d, (210, 1510), (750, 1120), CYAN)
    save("003-escalator-grooves/assets/scene-03-handoff.png", im)


def windshield_bond() -> None:
    im, d = canvas()
    d.rounded_rectangle((190, 400, 500, 1480), 70, fill=(78, 155, 190), outline=WHITE, width=12)
    d.rectangle((430, 520, 600, 1360), fill=(14, 19, 24))
    d.polygon([(590, 650), (780, 760), (780, 1230), (590, 1330)], fill=(35, 35, 40))
    d.polygon([(580, 760), (700, 825), (700, 1165), (580, 1230)], fill=AMBER)
    d.rounded_rectangle((720, 560, 930, 1420), 45, fill=(98, 112, 124), outline=STEEL, width=10)
    for y in (760, 940, 1120):
        arrow(d, (170, y), (420, y), CYAN, 14)
    save("004-windshield-frit/assets/scene-02-bond-cutaway.png", im)


def windshield_gradient() -> None:
    im, d = canvas()
    d.pieslice((160, 340, 1200, 1540), 90, 270, fill=(55, 130, 165), outline=WHITE, width=10)
    d.rectangle((160, 340, 350, 1540), fill=(8, 10, 14))
    for col in range(9):
        x = 360 + col * 58
        radius = max(5, 28 - col * 3)
        for y in range(480, 1450, 70):
            d.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(5, 7, 10))
    d.ellipse((700, 150, 940, 390), fill=AMBER)
    for x in (720, 790, 860):
        arrow(d, (x, 410), (x - 280, 680), AMBER, 10)
    save("004-windshield-frit/assets/scene-03-sun-gradient.png", im)


def container_compare() -> None:
    im, d = canvas()
    d.line((540, 300, 540, 1550), fill=(55, 85, 105), width=8)
    d.rectangle((170, 520, 430, 1330), fill=STEEL)
    d.arc((110, 700, 490, 1450), 260, 100, fill=RED, width=20)
    zigzag = []
    for y in range(500, 1350, 80):
        zigzag.extend([(680, y), (890, y + 40)])
    d.line(zigzag, fill=STEEL, width=48, joint="curve")
    for y in (620, 900, 1180):
        arrow(d, (950, y), (880, y), CYAN, 14)
        arrow(d, (620, y), (690, y), CYAN, 14)
    arrow(d, (300, 360), (300, 620), RED)
    arrow(d, (790, 360), (790, 620), CYAN)
    save("005-container-corrugation/assets/scene-02-flat-vs-folded.png", im)


def container_frame() -> None:
    im, d = canvas()
    d.rectangle((160, 390, 920, 1450), outline=STEEL, width=48)
    for x in range(220, 880, 70):
        d.line((x, 450, x + 35, 1390), fill=(75, 125, 155), width=25)
        d.line((x + 35, 450, x, 1390), fill=(75, 125, 155), width=25)
    for p in ((160, 390), (920, 390), (160, 1450), (920, 1450)):
        d.rounded_rectangle((p[0]-45, p[1]-45, p[0]+45, p[1]+45), 15, fill=AMBER)
    arrow(d, (70, 920), (300, 920), RED, 22)
    arrow(d, (1010, 920), (780, 920), RED, 22)
    save("005-container-corrugation/assets/scene-03-frame-bracing.png", im)


def keyboard_home() -> None:
    im, d = canvas()
    letters = "ASDFGHJKL"
    start_x, y, size, gap = 55, 820, 100, 12
    for i, letter in enumerate(letters):
        x = start_x + i * (size + gap)
        color = (60, 78, 95) if letter not in "FJ" else (28, 126, 160)
        d.rounded_rectangle((x, y, x + size, y + size), 16, fill=color, outline=WHITE, width=3)
        if letter in "FJ":
            d.rounded_rectangle((x + 25, y + 73, x + 75, y + 82), 4, fill=AMBER)
    d.ellipse((310, 610, 455, 790), fill=(221, 168, 126), outline=WHITE, width=5)
    d.ellipse((755, 610, 900, 790), fill=(221, 168, 126), outline=WHITE, width=5)
    arrow(d, (382, 780), (382, 850), AMBER, 12)
    arrow(d, (827, 780), (827, 850), AMBER, 12)
    save("006-keyboard-bumps/assets/scene-02-home-row.png", im)


def keyboard_map() -> None:
    im, d = canvas()
    for row in range(4):
        for col in range(10):
            x, y = 65 + col * 95 + row * 22, 620 + row * 130
            d.rounded_rectangle((x, y, x + 76, y + 86), 12, fill=(48, 66, 82), outline=(90, 120, 140), width=2)
    anchors = [(65 + 3 * 95 + 22, 620 + 2 * 130 + 43), (65 + 6 * 95 + 22, 620 + 2 * 130 + 43)]
    for ax, ay in anchors:
        for r, alpha_color in ((75, (25, 100, 130)), (45, (40, 160, 190)), (18, AMBER)):
            d.ellipse((ax-r, ay-r, ax+r, ay+r), fill=alpha_color)
        for endpoint in ((150, 480), (540, 420), (930, 500), (210, 1230), (850, 1260)):
            d.line((ax, ay, *endpoint), fill=CYAN, width=6)
    save("006-keyboard-bumps/assets/scene-03-touch-map.png", im)


def soda_pressure() -> None:
    im, d = canvas()
    d.rounded_rectangle((260, 310, 820, 1510), 180, outline=STEEL, width=38)
    d.arc((300, 1230, 780, 1650), 180, 360, fill=AMBER, width=40)
    center = (540, 900)
    for angle in range(0, 360, 30):
        end = (int(center[0] + 300 * math.cos(math.radians(angle))), int(center[1] + 430 * math.sin(math.radians(angle))))
        arrow(d, center, end, CYAN, 9)
    save("007-soda-can-dome/assets/scene-02-pressure-cutaway.png", im)


def soda_compare() -> None:
    im, d = canvas()
    d.line((540, 300, 540, 1560), fill=(55, 85, 105), width=8)
    d.rectangle((140, 520, 450, 1320), outline=STEEL, width=34)
    d.arc((140, 1150, 450, 1460), 180, 360, fill=RED, width=32)
    d.rectangle((630, 520, 940, 1320), outline=STEEL, width=34)
    d.arc((630, 1130, 940, 1450), 0, 180, fill=AMBER, width=32)
    for x in (295, 785):
        arrow(d, (x, 900), (x, 1190), CYAN, 15)
    save("007-soda-can-dome/assets/scene-03-flat-vs-dome.png", im)


def tape_pull() -> None:
    im, d = canvas()
    d.rectangle((130, 770, 850, 1030), fill=AMBER, outline=WHITE, width=8)
    d.rectangle((790, 650, 930, 1160), fill=STEEL)
    d.rectangle((910, 500, 1010, 1380), fill=(112, 77, 47))
    d.ellipse((720, 820, 810, 910), fill=(90, 100, 108), outline=WHITE, width=5)
    d.ellipse((720, 930, 810, 1020), fill=(90, 100, 108), outline=WHITE, width=5)
    arrow(d, (670, 600), (350, 600), CYAN, 18)
    save("008-tape-hook/assets/scene-02-pull-measure.png", im)


def tape_push() -> None:
    im, d = canvas()
    d.rectangle((230, 770, 950, 1030), fill=AMBER, outline=WHITE, width=8)
    d.rectangle((130, 650, 270, 1160), fill=STEEL)
    d.rectangle((70, 450, 150, 1400), fill=(118, 126, 130))
    d.ellipse((245, 820, 335, 910), fill=(90, 100, 108), outline=WHITE, width=5)
    d.ellipse((245, 930, 335, 1020), fill=(90, 100, 108), outline=WHITE, width=5)
    arrow(d, (700, 600), (310, 600), AMBER, 18)
    arrow(d, (330, 1240), (210, 1240), CYAN, 14)
    save("008-tape-hook/assets/scene-03-push-measure.png", im)


def main() -> None:
    for function in (
        train_circles, train_curve, escalator_comb, escalator_handoff,
        windshield_bond, windshield_gradient, container_compare, container_frame,
        keyboard_home, keyboard_map, soda_pressure, soda_compare, tape_pull, tape_push,
    ):
        function()


if __name__ == "__main__":
    main()

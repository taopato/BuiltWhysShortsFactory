"""A multi-shot, original 3D story about a tape measure's sliding hook.

This is a review pilot only. It never writes to the publishing queue.
Blender example: blender --background --python tape_story.py -- preview 130
                 blender --background --python tape_story.py -- render
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_pilot import OUT, box, common, cylinder, key, material, point_camera


FPS = 20
LAST = 810


def paint(name, color, metal=0.0, emission=0.0):
    return material(name, color, metal, 0.27 if metal else 0.48, emission)


def label(name, value, xyz, size, mat, rotate=(math.pi / 2, 0, 0)):
    bpy.ops.object.text_add(location=xyz, rotation=rotate)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = value
    obj.data.size = size
    obj.data.extrude = 0.002
    obj.data.materials.append(mat)
    return obj


def stage(x, blue, dark):
    box("Dark tabletop", (x, 0, 0.1), (8.2, 5.8, 0.15), dark, 0.12)
    box("Stage accent stripe", (x, 2.76, 0.2), (7.8, 0.015, 0.015), blue, 0.01)
    if x:
        for offset, power, color, size in (
            ((-3, -4, 7), 1500, (0.35, 0.78, 1.0), 5.0),
            ((4, 2, 5), 1450, (1.0, 0.47, 0.17), 4.0),
        ):
            bpy.ops.object.light_add(type="AREA", location=(x + offset[0], offset[1], offset[2]))
            light = bpy.context.object
            light.data.energy = power
            light.data.shape = "DISK"
            light.data.size = size
            light.data.color = color
            point_camera(light, (x, 0, 1.3))


def tape(x, y, name, blade, ink, chrome, orange, *, reverse=False, length=4.4):
    direction = -1 if reverse else 1
    # All dimensions are authored in scene units rather than copied footage.
    blade_center = x + direction * (length / 2 - 0.02)
    body = box(f"{name}: yellow steel blade", (blade_center, y, 1.18), (length, 0.52, 0.045), blade, 0.03)
    for i in range(1, 21):
        local = 0.22 * i
        if local > length - 0.15:
            break
        xx = x + direction * local
        tick = box(f"{name}: measurement tick {i}", (xx, y - 0.12, 1.245), (0.018, 0.14 if i % 5 else 0.28, 0.014), ink, 0.002)
        if i % 5 == 0:
            label(f"{name}: numeral {i // 5}", str(i // 5), (xx - 0.09, y + 0.02, 1.258), 0.14, ink, (0, 0, 0))
    bpy.ops.object.empty_add(location=(x, y, 1.18))
    hook = bpy.context.object
    hook.name = name + ": sliding hook"
    plate = box(name + ": slotted chrome plate", (0, 0, 0.08), (0.75, 0.60, 0.065), chrome, 0.035)
    plate.parent = hook
    lip = box(name + ": bent catch lip", (-0.37 * direction, 0, -0.33), (0.075, 0.64, 0.72), chrome, 0.02)
    lip.parent = hook
    for xx in (-0.18, 0.20):
        slot = box(name + ": elongated rivet slot", (xx, 0, 0.174), (0.19, 0.15, 0.025), ink, 0.025)
        slot.parent = hook
        rivet = cylinder(name + ": fixed rivet", (xx, 0, 0.215), 0.095, 0.030, orange, vertices=24)
        rivet.parent = hook
    return hook, body


def arrow(x, y, z, length, mat, name):
    shaft = box(name + " shaft", (x, y, z), (length, 0.05, 0.045), mat, 0.02)
    tip = box(name + " tip", (x + length / 2 + 0.08, y, z), (0.20, 0.16, 0.05), mat, 0.02)
    tip.rotation_euler.z = math.radians(45)
    return shaft, tip


def set_camera(camera, target, start, end, pos0, pos1, look0, look1, zoom0, zoom1):
    key(camera, start, location=pos0)
    key(camera, end, location=pos1)
    key(target, start, location=look0)
    key(target, end, location=look1)
    camera.data.ortho_scale = zoom0
    camera.data.keyframe_insert("ortho_scale", frame=start)
    camera.data.ortho_scale = zoom1
    camera.data.keyframe_insert("ortho_scale", frame=end)


def build():
    scene, camera, target = common((1.0, 0.42, 0.08))
    scene.render.resolution_x, scene.render.resolution_y = 480, 854
    scene.frame_end = LAST
    scene.render.fps = FPS
    dark = paint("Graphite stage", (0.012, 0.026, 0.042), 0.25)
    chrome = paint("Brushed bright metal", (0.55, 0.69, 0.77), 0.88)
    blade = paint("Safety yellow blade", (0.95, 0.61, 0.09), 0.6)
    ink = paint("Ink markings", (0.016, 0.025, 0.045))
    orange = paint("Orange measurement contact", (1, 0.25, 0.035), 0.15, 0.7)
    blue = paint("Cyan correct measurement", (0.04, 0.65, 0.95), 0.1, 0.8)
    red = paint("Red error signal", (0.95, 0.06, 0.055), 0.1, 0.8)
    wood = paint("Warm wood block", (0.35, 0.19, 0.09), 0.1)
    wall = paint("Concrete wall", (0.37, 0.43, 0.48), 0.05)

    # Shot 1. Tight macro: a loose-looking hook wiggles, then the two slots
    # and two rivets are revealed with a fast camera move.
    stage(0, blue, dark)
    hook0, _ = tape(-1.9, 0, "Macro hook", blade, ink, chrome, orange)
    for frame, dx in ((1, -0.10), (16, 0.09), (29, -0.07), (42, 0.09), (58, 0.0), (110, 0.0)):
        key(hook0, frame, location=(-1.9 + dx, 0, 1.18))

    # Shot 2. A box edge catches the hook while the blade is pulled away.
    stage(12, blue, dark)
    box("Outside measured object", (10.05, 0, 1.1), (1.15, 1.6, 1.85), wood, 0.07)
    box("Outside edge glow", (10.63, 0, 2.04), (0.03, 1.56, 0.03), orange, 0.01)
    h2, b2 = tape(10.66, -0.1, "Pull outside", blade, ink, chrome, orange, length=5.5)
    key(h2, 112, location=(10.78, -0.1, 1.18))
    key(h2, 157, location=(10.60, -0.1, 1.18))
    key(h2, 258, location=(10.60, -0.1, 1.18))
    arrow(13.55, -1.45, 1.35, 1.2, blue, "Pull direction")
    label("Outside measuring label", "PULL FROM AN EDGE", (10.0, 1.55, 1.15), 0.24, chrome, (0, 0, 0))

    # Shot 3. A wall pushes the hook inward. The wall and hook take up the
    # same thickness; the other end of the tape remains extended.
    stage(25, blue, dark)
    box("Left interior wall", (22.05, 0, 1.2), (0.52, 2.2, 2.45), wall, 0.025)
    box("Right interior wall", (27.87, 0, 1.2), (0.52, 2.2, 2.45), wall, 0.025)
    box("Wall contact signal", (27.6, 0, 1.6), (0.027, 1.85, 0.9), orange, 0.01)
    h3, _ = tape(27.43, 0, "Push inside", blade, ink, chrome, orange, reverse=True, length=5.0)
    key(h3, 259, location=(27.25, 0, 1.18))
    key(h3, 326, location=(27.48, 0, 1.18))
    key(h3, 420, location=(27.48, 0, 1.18))
    arrow(23.6, -1.30, 1.34, 1.25, orange, "Push direction")
    label("Inside measuring label", "PUSH INTO THE WALL", (22.6, 1.75, 1.20), 0.23, chrome, (0, 0, 0))

    # Shot 4. An enlarged exploded view makes the moving part legible.
    stage(38, blue, dark)
    h4, _ = tape(36.3, 0, "Mechanism closeup", blade, ink, chrome, orange)
    for f, dx in ((421, 0), (455, 0.23), (485, -0.20), (515, 0.20), (555, -0.17), (634, 0)):
        key(h4, f, location=(36.3 + dx, 0, 1.18))
    box("Exposed thickness sample", (38.55, -1.13, 1.2), (0.22, 0.58, 0.40), chrome, 0.02)
    arrow(37.20, -1.33, 1.30, 0.85, orange, "Travel equals thickness")
    label("Thickness equals travel", "SLIDE = HOOK THICKNESS", (36.0, 1.6, 1.20), 0.22, chrome, (0, 0, 0))

    # Shot 5. A hypothetical fixed hook gives a mismatched zero point.
    stage(63, red, dark)
    box("Wrong example wall", (60.2, 0, 1.1), (0.62, 1.7, 1.7), wall, 0.04)
    tape(60.55, 0, "Incorrect fixed hook", blade, ink, chrome, orange, length=4.8)
    box("Wrong zero line", (60.86, -0.15, 1.26), (0.025, 0.75, 0.09), red, 0.01)
    label("Fixed is inaccurate", "FIXED HOOK = OFFSET", (60.4, 1.45, 1.25), 0.23, red, (0, 0, 0))

    # Shot 6. Two complete measuring examples side by side. The hook moves
    # in opposite directions and both examples resolve at the same zero.
    stage(51, blue, dark)
    box("Final outside block", (48.45, -0.95, 1.05), (0.65, 0.8, 1.50), wood, 0.04)
    box("Final inside wall", (48.45, 0.95, 1.05), (0.65, 0.8, 1.50), wall, 0.04)
    h5a, _ = tape(48.83, -0.95, "Final pull example", blade, ink, chrome, orange, length=4.2)
    h5b, _ = tape(48.83, 0.95, "Final push example", blade, ink, chrome, orange, length=4.2)
    for f, out_x, in_x in ((701, 48.92, 48.71), (750, 48.70, 48.93), (810, 48.70, 48.93)):
        key(h5a, f, location=(out_x, -0.95, 1.18))
        key(h5b, f, location=(in_x, 0.95, 1.18))
    label("Pull caption in scene", "OUTSIDE  /  PULL", (49.0, -1.6, 1.29), 0.20, chrome, (0, 0, 0))
    label("Push caption in scene", "INSIDE  /  PUSH", (49.0, 1.34, 1.29), 0.20, chrome, (0, 0, 0))

    # The consecutive end/start frames are deliberate hard cuts, with a
    # moving camera inside each shot. No stationary 40-second product spin.
    shots = [
        (1, 40, (-0.5, -5.5, 4.3), (-0.9, -5.0, 3.6), (-2.0, 0, 1.2), (-1.95, 0, 1.2), 4.2, 3.2),
        (41, 111, (1.1, -6.2, 4.5), (0.1, -5.0, 3.3), (-1.15, 0, 1.2), (-1.65, 0, 1.2), 5.2, 3.6),
        (112, 172, (14.0, -7.2, 5.3), (13.2, -6.9, 4.8), (12.0, 0, 1.1), (12.0, 0, 1.1), 6.2, 5.5),
        (173, 258, (11.4, -5.7, 4.2), (12.6, -6.2, 4.5), (11.0, 0, 1.1), (12.0, 0, 1.1), 3.9, 5.2),
        (259, 322, (28.3, -7.8, 5.2), (27.3, -7.2, 5.0), (25.0, 0, 1.1), (25.0, 0, 1.1), 6.9, 6.2),
        (323, 420, (24.2, -6.2, 4.2), (25.1, -6.5, 4.7), (26.7, 0, 1.1), (26.5, 0, 1.1), 4.4, 5.2),
        (421, 518, (39.8, -5.8, 4.2), (38.3, -5.0, 3.5), (36.5, 0, 1.2), (36.4, 0, 1.2), 4.2, 3.4),
        (519, 634, (36.7, -4.4, 3.3), (37.4, -4.8, 3.2), (36.1, 0, 1.2), (36.4, 0, 1.2), 2.7, 2.8),
        (635, 700, (65.5, -7.2, 5.3), (64.5, -6.2, 4.7), (62.7, 0, 1.2), (62.7, 0, 1.2), 6.2, 5.0),
        (701, 810, (53.5, -7.2, 5.3), (52.5, -6.2, 4.7), (50.7, 0, 1.2), (50.7, 0, 1.2), 6.5, 5.5),
    ]
    for s, e, p0, p1, l0, l1, z0, z1 in shots:
        set_camera(camera, target, s, e, p0, p1, l0, l1, z0, z1)
    return scene


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    mode = args[0] if args else "preview"
    if mode not in {"preview", "render"}:
        raise SystemExit("Use preview [frame] or render [first-frame] [last-frame]")
    OUT.mkdir(parents=True, exist_ok=True)
    scene = build()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "tape-story.blend"))
    if mode == "preview":
        for frame in (int(value) for value in args[1:]) if len(args) > 1 else (1,):
            scene.frame_set(frame)
            scene.render.filepath = str(OUT / f"tape-story-preview-{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
    else:
        frames = OUT / "tape-frames"
        frames.mkdir(parents=True, exist_ok=True)
        if len(args) > 1:
            scene.frame_start = int(args[1])
        if len(args) > 2:
            scene.frame_end = int(args[2])
        scene.render.filepath = str(frames / "frame_")
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()

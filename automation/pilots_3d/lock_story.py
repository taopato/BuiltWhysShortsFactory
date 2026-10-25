"""Original 3D pin-tumbler lock explainer, intentionally isolated from publishing.

The cutaway is a simplified educational model. It shows why the correct key
aligns the key-pin/driver-pin junction with the plug's shear line; it does not
demonstrate lock bypass.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_pilot import OUT, box, common, cylinder, key, material, point_camera, torus


FPS = 20
LAST = 600
SHEAR = 1.68
PIN_X = (-1.35, -0.68, 0.0, 0.68, 1.35)


def mat(name, color, metallic=0.0, roughness=0.35, glow=0.0):
    return material(name, color, metallic, roughness, glow)


def text_obj(name, message, loc, size, ink):
    bpy.ops.object.text_add(location=loc, rotation=(math.pi / 2, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.data.body = message
    obj.data.size = size
    obj.data.extrude = 0.002
    obj.data.materials.append(ink)
    return obj


def light_stage(x, accent):
    for pos, power, color, size in (
        ((-3.8, -4, 6.5), 1250, (0.35, 0.72, 1.0), 4.6),
        ((3.8, 2.4, 5.5), 1450, accent, 4.0),
        ((1.3, -4.2, 2.5), 310, (1.0, 0.42, 0.14), 2.2),
    ):
        bpy.ops.object.light_add(type="AREA", location=(x + pos[0], pos[1], pos[2]))
        lamp = bpy.context.object
        lamp.data.energy = power
        lamp.data.shape = "DISK"
        lamp.data.size = size
        lamp.data.color = color
        point_camera(lamp, (x, 0, 1.3))


def stage(x, floor, accent):
    box("Studio platform", (x, 0, 0.1), (9.2, 6.4, 0.16), floor, 0.1)
    box("Glowing platform edge", (x, -2.95, 0.22), (8.8, 0.025, 0.018), accent, 0.015)
    light_stage(x, (0.9, 0.48, 0.2))


def add_spring(name, x, y, z0, height, steel):
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.018
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    turns = 7
    points = 84
    spline.points.add(points - 1)
    for i, item in enumerate(spline.points):
        t = i / (points - 1)
        angle = t * math.tau * turns
        item.co = (x + math.cos(angle) * 0.12, y + math.sin(angle) * 0.12, z0 + t * height, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(steel)
    return obj


def make_key(prefix, x, y, z, brass, edge, *, proper):
    bpy.ops.object.empty_add(location=(x, y, z))
    root = bpy.context.object
    root.name = prefix + " / key root"
    # Key tip points right. Distinct pin-height teeth make the educational
    # cutaway legible; they are not a real key code or dimensional template.
    blade = box(prefix + " / brass blade", (0, 0, 0), (4.6, 0.48, 0.14), brass, 0.06)
    blade.parent = root
    tip = box(prefix + " / tapered tip", (2.32, 0, 0), (0.32, 0.43, 0.13), edge, 0.06)
    tip.parent = root
    heights = (0.43, 0.26, 0.36, 0.18, 0.31) if proper else (0.23, 0.43, 0.20, 0.40, 0.16)
    for idx, px in enumerate(PIN_X):
        tooth = box(prefix + f" / bitting {idx+1}", (px, 0, 0.13 + heights[idx] / 2),
                    (0.43, 0.43, heights[idx]), brass, 0.035)
        tooth.parent = root
    handle = torus(prefix + " / ring handle", (-2.8, 0, 0), 0.53, 0.14, brass,
                   (math.pi / 2, 0, 0))
    handle.parent = root
    return root


def mechanism(name, x, floor, steel, dark, blue, orange, red, brass, *, proper, start, finish):
    stage(x, floor, blue if proper else red)
    # Open cross-section rather than a solid cylinder so both levels of pins
    # remain visible at Shorts phone size.
    box(name + " / lower plug rail", (x, 0.3, 0.45), (4.9, 1.45, 0.34), steel, 0.12)
    box(name + " / back plug cheek", (x, 0.95, 1.18), (5.05, 0.12, 1.15), dark, 0.07)
    box(name + " / upper housing back rail", (x, 0.96, 2.60), (5.2, 0.20, 0.46), dark, 0.08)
    box(name + " / upper housing roof", (x, 0.45, 2.89), (5.2, 1.17, 0.13), steel, 0.05)
    box(name + " / left bearing", (x-2.55, 0.3, 1.42), (0.21, 1.5, 2.5), steel, 0.06)
    box(name + " / right bearing", (x+2.55, 0.3, 1.42), (0.21, 1.5, 2.5), steel, 0.06)
    shear = box(name + " / shear line", (x, -0.54, SHEAR), (4.75, 0.035, 0.026), blue if proper else red, 0.008)
    key_root = make_key(name, x-5.9, -0.08, 0.70, brass, steel, proper=proper)
    if start is not None:
        key(key_root, start, location=(x-5.9, -0.08, 0.70))
        key(key_root, finish, location=(x, -0.08, 0.70))
    else:
        key_root.location = (x, -0.08, 0.70)
    lower_lengths = (0.55, 0.72, 0.62, 0.80, 0.67)
    offsets = (0, 0, 0, 0, 0) if proper else (0.12, -0.16, 0.22, -0.08, 0.14)
    pin_parts = []
    for i, local_x in enumerate(PIN_X):
        px = x + local_x
        height = lower_lengths[i]
        base_top = SHEAR - 0.20
        end_top = SHEAR + offsets[i]
        lower = cylinder(name + f" / key pin {i+1}", (px, -0.11, base_top-height/2),
                         0.19, height, blue, vertices=36)
        driver = cylinder(name + f" / driver pin {i+1}", (px, -0.11, base_top+0.24),
                          0.18, 0.42, orange, vertices=36)
        add_spring(name + f" / spring {i+1}", px, -0.11, 2.0, 0.42, steel)
        pin_parts.append((lower, driver, px, height, base_top, end_top))
        if start is not None:
            key(lower, start, location=(px, -0.11, base_top-height/2))
            key(driver, start, location=(px, -0.11, base_top+0.24))
            rise = start + int((finish-start)*(i+1)/6)
            key(lower, rise, location=(px, -0.11, end_top-height/2))
            key(driver, rise, location=(px, -0.11, end_top+0.24))
    return key_root, pin_parts, shear


def camera_shot(cam, target, first, last, p0, p1, look0, look1, z0, z1):
    key(cam, first, location=p0)
    key(cam, last, location=p1)
    key(target, first, location=look0)
    key(target, last, location=look1)
    cam.data.ortho_scale = z0
    cam.data.keyframe_insert("ortho_scale", frame=first)
    cam.data.ortho_scale = z1
    cam.data.keyframe_insert("ortho_scale", frame=last)


def build():
    scene, cam, target = common((1, 0.44, 0.15))
    scene.render.resolution_x = 480
    scene.render.resolution_y = 854
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = LAST
    floor = mat("Near-black studio", (0.009, 0.020, 0.038), 0.2)
    steel = mat("Brushed steel", (0.39, 0.51, 0.62), 0.88, 0.27)
    dark = mat("Graphite casing", (0.07, 0.12, 0.18), 0.65, 0.31)
    blue = mat("Unlocked blue", (0.035, 0.68, 0.97), 0.25, 0.22, 0.65)
    orange = mat("Driver copper", (0.98, 0.39, 0.11), 0.6, 0.25)
    red = mat("Blocked red", (0.98, 0.075, 0.055), 0.15, 0.2, 0.75)
    brass = mat("Warm brass key", (0.91, 0.61, 0.23), 0.8, 0.26)
    wood = mat("Walnut door", (0.22, 0.105, 0.05), 0.05, 0.5)

    # Beat 1: exterior cylinder and key, with no internal parts visible yet.
    stage(0, floor, orange)
    door = box("Door front", (0, 0.8, 1.5), (6.2, 0.36, 3.5), wood, 0.08)
    escutcheon = cylinder("Round exterior plate", (0, 0.47, 1.58), 1.02, 0.13, steel,
                          (math.pi/2, 0, 0), 80)
    deep_black = mat("Unlit keyway", (0.001, 0.003, 0.006), 0.0, 0.9)
    cylinder("Dark keyway barrel", (0, 0.29, 1.58), 0.69, 0.14, dark,
             (math.pi/2, 0, 0), 64)
    box("Keyhole narrow slot", (0, 0.19, 1.58), (0.12, 0.025, 0.65), deep_black, 0.025)
    box("Keyhole lower shelf", (0, 0.17, 1.22), (0.39, 0.025, 0.09), deep_black, 0.025)
    light_stage(0, (1.0, 0.55, 0.25))

    # Beat 2: wrong key leaves the driver pins crossing the shear line.
    mechanism("Wrong key cutaway", 12, floor, steel, dark, blue, orange, red, brass,
              proper=False, start=59, finish=159)

    # Beat 3: correct key's bitting lifts pins to five matched junctions.
    good_key, pin_parts, shear = mechanism("Correct key cutaway", 25, floor,
                                         steel, dark, blue, orange, red, brass,
                                         proper=True, start=160, finish=310)
    # A second, brighter line appears when all five divisions match.
    signal = box("Alignment flash", (25, -0.62, SHEAR), (4.9, 0.06, 0.055), blue, 0.01)
    key(signal, 160, scale=(0.01, 1, 1))
    key(signal, 315, scale=(1, 1, 1))
    key(signal, 380, scale=(1, 1, 1))

    # Beat 4: unlocked plug turns and a cam carries the motion to the bolt.
    stage(38, floor, blue)
    box("Plug housing back", (38, 0.58, 1.53), (4.1, 0.25, 2.25), dark, 0.09)
    cylinder("Plug fixed rim", (38, -0.10, 1.52), 1.1, 0.18, steel, (math.pi/2, 0, 0), 80)
    bpy.ops.object.empty_add(location=(38, -0.38, 1.52))
    rotating = bpy.context.object
    rotating.name = "Plug and key rotate"
    face = cylinder("Plug rotating face", (38, -0.38, 1.52), 0.86, 0.10, dark,
                    (math.pi/2, 0, 0), 80)
    face.parent = rotating
    face.location = (0, 0, 0)
    slot = box("Rotating keyway", (38, -0.48, 1.52), (0.15, 0.05, 1.12), brass, 0.04)
    slot.parent = rotating
    slot.location = (0, -0.1, 0)
    for f, angle in ((381, 0), (420, 0), (465, -math.pi/3), (485, -math.pi/3)):
        key(rotating, f, rotation=(0, angle, 0))
    shaft = cylinder("Motion shaft", (40.0, 0.38, 1.52), 0.18, 2.6, steel,
                     (0, math.pi/2, 0), 48)
    # Visible cam and sliding bolt at the far end.
    stage(51, floor, orange)
    cam_disk = cylinder("Back of lock cam", (49.55, -1.05, 1.55), 0.85, 0.18, steel,
                   (math.pi/2, 0, 0), 64)
    bpy.ops.object.empty_add(location=(49.55, -1.22, 1.55))
    cam_root = bpy.context.object
    cam_root.name = "Cam rotates"
    nub = box("Offset cam tooth", (50.15, -1.24, 1.55), (0.62, 0.14, 0.20), brass, 0.07)
    nub.parent = cam_root
    nub.location = (0.60, 0, 0)
    for f, angle in ((486, 0), (520, -math.pi/3), (600, -math.pi/3)):
        key(cam_root, f, rotation=(0, angle, 0))
    box("Door frame receiver", (53.0, 0.0, 1.55), (0.60, 1.1, 1.5), wood, 0.06)
    bolt = box("Sliding deadbolt", (52.1, -0.05, 1.55), (2.35, 0.70, 0.75), steel, 0.08)
    key(bolt, 486, location=(52.1, -0.05, 1.55))
    key(bolt, 560, location=(50.75, -0.05, 1.55))
    key(bolt, 600, location=(50.75, -0.05, 1.55))

    # Camera beats are chosen to follow individual causal changes. Narration
    # and titles are timed separately by the composition script.
    shots = [
        (1, 58, (3.8,-7.4,4.0), (2.3,-5.7,3.6), (0,0,1.55), (0,0,1.55), 5.2, 4.1),
        (59, 113, (15.2,-7.7,4.5), (14.0,-6.7,4.0), (12,0,1.5), (12,0,1.5), 5.9, 5.2),
        (114, 159, (10.5,-6.2,3.6), (13.4,-5.5,3.5), (12,0,1.5), (12,0,1.5), 4.5, 4.3),
        (160, 222, (28.1,-7.6,4.4), (27.6,-6.9,4.1), (25,0,1.5), (25,0,1.5), 5.8, 5.2),
        (223, 310, (23.5,-5.6,3.7), (24.5,-5.0,3.4), (25,0,1.6), (25,0,1.6), 4.0, 3.6),
        (311, 380, (27.7,-6.4,3.4), (26.0,-5.1,3.1), (25,0,1.7), (25,0,1.7), 4.3, 3.0),
        (381, 432, (40.4,-7.2,4.0), (39.3,-5.8,3.5), (38,0,1.5), (38,0,1.5), 4.7, 3.6),
        (433, 485, (36.0,-5.5,3.6), (38.9,-5.2,3.4), (38,0,1.5), (38,0,1.5), 3.4, 3.1),
        (486, 540, (51.8,-8.5,4.2), (51.5,-7.4,3.9), (51,0,1.5), (51,0,1.5), 9.5, 8.8),
        (541, 600, (51.0,-7.6,3.9), (51.0,-7.2,3.8), (51,0,1.5), (51,0,1.5), 8.8, 8.5),
    ]
    for args in shots:
        camera_shot(cam, target, *args)
    return scene


def main():
    args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    mode = args[0] if args else "preview"
    if mode not in {"preview", "render"}:
        raise SystemExit("preview <frames...> or render [start [end]]")
    OUT.mkdir(parents=True, exist_ok=True)
    scene = build()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "lock-story.blend"))
    if mode == "preview":
        for frame in map(int, args[1:] or [1]):
            scene.frame_set(frame)
            scene.render.filepath = str(OUT / f"lock-preview-{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
    else:
        if len(args)>1:
            scene.frame_start = int(args[1])
        if len(args)>2:
            scene.frame_end = int(args[2])
        frames = OUT / "lock-frames"
        frames.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(frames / "frame_")
        bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()

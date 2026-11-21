"""Isolated cutaway shot: one key physically raises five pin pairs.

This is a review asset, not a publication job. Run in Blender 4.3+ with
``--python lock_causal_shot_v5.py -- preview``. Geometry is original and
illustrative; the final video still needs technical and visual review.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

FPS = 24
SECONDS = 5
PIN_X = (-0.80, -0.40, 0.0, 0.40, 0.80)
LOWER_LENGTHS = (0.32, 0.40, 0.28, 0.36, 0.31)
LIFTS = (0.22, 0.21, 0.20, 0.22, 0.21)
SHEAR = 0.50


def mat(name, color, metallic=0.0, roughness=0.4, alpha=1.0):
    obj = bpy.data.materials.new(name)
    obj.diffuse_color = (*color, alpha)
    obj.use_nodes = True
    principled = obj.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (*color, alpha)
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Roughness"].default_value = roughness
    return obj


def cube(name, location, scale, material, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Machined edge", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    obj.data.materials.append(material)
    return obj


def cylinder(name, location, radius, depth, material, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    bevel = obj.modifiers.new("Soft metal rim", "BEVEL")
    bevel.width = 0.008
    bevel.segments = 2
    obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def spring(name, x, lower_z, upper_z, material):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.007
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    count = 72
    spline.points.add(count - 1)
    for i, point in enumerate(spline.points):
        t = i / (count - 1)
        a = t * math.tau * 4.5
        point.co = (0.028 * math.cos(a), 0.028 * math.sin(a), t, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = (x, -0.08, lower_z)
    obj.scale.z = upper_z - lower_z
    obj.data.materials.append(material)
    return obj


def key_blade(material):
    # Five top heights are paired with five lower-pin lengths. The visible
    # blade enters from the left; each notch reaches its pin in turn.
    top = [(-1.13, -0.02)]
    for x, length in zip(PIN_X, LOWER_LENGTHS):
        top += [(x - 0.13, SHEAR - length - 0.025), (x, SHEAR - length), (x + 0.13, SHEAR - length - 0.025)]
    top += [(1.12, -0.02)]
    outline = [(-1.13, -0.32), (1.12, -0.32)] + list(reversed(top))
    vertices = [(x, y, z) for y in (-0.11, 0.11) for x, z in outline]
    n = len(outline)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    mesh = bpy.data.meshes.new("Cut-to-fit key profile")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    key = bpy.data.objects.new("One real moving key blade", mesh)
    bpy.context.collection.objects.link(key)
    key.data.materials.append(material)
    bevel = key.modifiers.new("Stamped key edge", "BEVEL")
    bevel.width = 0.008
    bevel.segments = 2
    key.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return key, top


def key_height(top, local_x):
    """Height of the moving key's actual cut profile at a pin chamber."""
    if local_x < top[0][0] or local_x > top[-1][0]:
        return None
    for (xa, za), (xb, zb) in zip(top, top[1:]):
        if xa <= local_x <= xb:
            ratio = (local_x - xa) / (xb - xa)
            return za * (1 - ratio) + zb * ratio
    return None


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def point(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def build():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 1280
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = FPS * SECONDS
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.world.color = (0.015, 0.022, 0.034)

    dark = mat("Cutaway background", (0.025, 0.043, 0.065), 0.1, 0.75)
    body = mat("Machined steel housing", (0.21, 0.29, 0.34), 0.75, 0.28)
    brass = mat("Warm key pins", (0.63, 0.38, 0.12), 0.85, 0.24)
    steel = mat("Driver pins and springs", (0.63, 0.72, 0.78), 0.76, 0.24)
    key_mat = mat("Brushed graphite key", (0.08, 0.11, 0.14), 0.62, 0.48)
    cyan = mat("Shear reference", (0.035, 0.69, 0.84), 0.15, 0.32)
    cube("Studio ground", (0, 0.65, -0.66), (3.3, 1.4, 0.10), dark, 0.03)
    cube("Housing rear", (0, 0.20, 0.35), (2.56, 0.13, 1.55), body, 0.035)
    cube("Core rear cutaway", (0, 0.05, -0.11), (2.46, 0.14, 0.57), brass, 0.035)
    cube("Keyway lower lip", (0, -0.12, -0.41), (2.46, 0.12, 0.07), body, 0.015)
    cube("Upper chamber rail", (0, -0.015, 1.12), (2.46, 0.25, 0.18), body, 0.02)
    cube("Shear-line light guide", (0, -0.154, SHEAR), (2.48, 0.018, 0.012), cyan)
    cube("Left keyway", (-1.29, -0.03, -0.20), (0.07, 0.32, 0.53), body, 0.01)

    key, key_top = key_blade(key_mat)
    bow = cylinder("Key bow", (-1.25, -0.01, -0.10), 0.20, 0.07, key_mat)
    bow.rotation_euler = (math.pi / 2, 0, 0)
    bow.parent = key
    bow.matrix_parent_inverse = key.matrix_world.inverted()
    pin_parts = []
    for i, (x, length, lift) in enumerate(zip(PIN_X, LOWER_LENGTHS, LIFTS)):
        lower = cylinder(f"Key pin {i + 1}", (x, -0.08, SHEAR - lift - length / 2), 0.066, length, brass)
        driver = cylinder(f"Driver pin {i + 1}", (x, -0.08, SHEAR - lift + 0.15), 0.066, 0.30, steel)
        coil = spring(f"Spring {i + 1}", x, SHEAR + 0.31 - lift, 1.01, steel)
        pin_parts.append((lower, driver, coil, lift, length))
    for frame in range(1, FPS * SECONDS + 1):
        t = (frame - 1) / FPS
        progress = smooth((t - 0.25) / 3.15)
        key_x = -2.40 + 2.40 * progress
        key.location.x = key_x
        key.keyframe_insert(data_path="location", frame=frame)
        for x, (lower, driver, coil, lift, length) in zip(PIN_X, pin_parts):
            resting_bottom = SHEAR - length - lift
            surface = key_height(key_top, x - key_x)
            raised = max(0.0, surface - resting_bottom) if surface is not None else 0.0
            lower.location.z = SHEAR - lift + raised - length / 2
            driver.location.z = SHEAR - lift + raised + 0.15
            # The spring's lower endpoint follows the driver while its upper
            # endpoint stays fixed in the housing.
            coil.location.z = SHEAR + 0.31 - lift + raised
            coil.scale.z = 1.01 - coil.location.z
            lower.keyframe_insert(data_path="location", frame=frame)
            driver.keyframe_insert(data_path="location", frame=frame)
            coil.keyframe_insert(data_path="location", frame=frame)
            coil.keyframe_insert(data_path="scale", frame=frame)

    # The cut heights, not a timed animation cue, must leave every lower/driver
    # seam on the shear line when the key is fully inserted.
    scene.frame_set(FPS * SECONDS)
    for lower, driver, _coil, _lift, length in pin_parts:
        seam = lower.location.z + length / 2
        driver_bottom = driver.location.z - 0.15
        if abs(seam - SHEAR) > 0.003 or abs(driver_bottom - seam) > 0.003:
            raise RuntimeError("key profile failed to align a pin pair at the shear line")

    bpy.ops.object.camera_add(location=(0, -5.5, 0.62))
    camera = bpy.context.object
    camera.name = "Side cutaway sees key and pins together"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 4.62
    point(camera, (0, 0, 0.43))
    scene.camera = camera
    for name, loc, power, color, size in (
        ("Large key light", (-2.0, -3.0, 3.0), 520, (0.70, 0.83, 1.0), 3.0),
        ("Warm rim", (1.8, 1.2, 2.0), 450, (1.0, 0.72, 0.42), 2.3),
        ("Front fill", (0.0, -2.3, -0.1), 190, (0.55, 0.86, 1.0), 2.1),
    ):
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.name = name
        light.data.energy = power
        light.data.color = color
        light.data.shape = "DISK"
        light.data.size = size
        point(light, (0, 0, 0.3))
    return scene


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("build", "preview"))
    parser.add_argument("--out", type=Path, required=True)
    options = parser.parse_args(args)
    options.out.mkdir(parents=True, exist_ok=True)
    scene = build()
    bpy.ops.wm.save_as_mainfile(filepath=str(options.out / "lock-causal-v5.blend"))
    if options.mode == "preview":
        scene.eevee.taa_render_samples = 8
        for frame in (1, 25, 49, 73, 97, 120):
            scene.frame_set(frame)
            scene.render.filepath = str(options.out / f"preview-{frame:03d}.png")
            bpy.ops.render.render(write_still=True)
            print(f"PREVIEW {frame}", flush=True)


if __name__ == "__main__":
    main()

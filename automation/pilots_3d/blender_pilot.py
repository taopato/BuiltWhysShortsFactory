"""Two original BuiltWhys 3D storyboard pilots.

Run with Blender in background mode. This is deliberately separate from the
production publisher: the rendered videos must be reviewed before integration.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


FPS = 20
SECONDS = 20
FRAMES = FPS * SECONDS
SIZE = (480, 854)
OUT = Path(__file__).resolve().parents[2] / "storage" / "3d-pilots"


def material(name, color, metallic=0.0, roughness=0.4, emission=0.0):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1)
    result.use_nodes = True
    bsdf = result.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = emission
    return result


def box(name, location, scale, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new("Rounded edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    obj.data.materials.append(mat)
    return obj


def cylinder(name, location, radius, depth, mat, rotation=(0, 0, 0), vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    modifier = obj.modifiers.new("Edge highlights", "BEVEL")
    modifier.width = min(0.055, radius * 0.12)
    modifier.segments = 2
    obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def torus(name, location, major, minor, mat, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=64, minor_segments=12, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def key(obj, frame, location=None, rotation=None, scale=None, hide=None):
    if location is not None:
        obj.location = location
        obj.keyframe_insert(data_path="location", frame=frame)
    if rotation is not None:
        obj.rotation_euler = rotation
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert(data_path="scale", frame=frame)
    if hide is not None:
        obj.hide_render = hide
        obj.keyframe_insert(data_path="hide_render", frame=frame)


def point_camera(camera, target):
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def common(accent):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, FRAMES
    # Blender 5.2 removed direct FFmpeg output; image sequences are also safer
    # when a render needs to resume after an interruption.
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.use_nodes = True
    world_bg = scene.world.node_tree.nodes.get("Background")
    world_bg.inputs["Color"].default_value = (0.003, 0.008, 0.018, 1)
    world_bg.inputs["Strength"].default_value = 0.32
    ground = material("Midnight floor", (0.009, 0.018, 0.035), 0.25, 0.3)
    box("Studio floor", (0, 0, -0.3), (20, 20, 0.18), ground, 0.1)
    for location, power, color, size in (
        ((-3, -4, 7), 1100, (0.28, 0.7, 1.0), 5.0),
        ((4, 2, 5), 1350, accent, 4.0),
        ((1, -5, 2), 350, (1.0, 0.4, 0.14), 2.0),
    ):
        bpy.ops.object.light_add(type="AREA", location=location)
        light = bpy.context.object
        light.data.energy = power
        light.data.shape = "DISK"
        light.data.size = size
        light.data.color = color
        point_camera(light, (0, 0, 1.3))
    bpy.ops.object.camera_add(location=(5, -9, 5))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 7.8
    scene.camera = camera
    bpy.ops.object.empty_add(location=(0, 0, 1.3))
    target = bpy.context.object
    target.name = "Camera target"
    follow = camera.constraints.new(type="TRACK_TO")
    follow.target = target
    follow.track_axis = "TRACK_NEGATIVE_Z"
    follow.up_axis = "UP_Y"
    return scene, camera, target


def seatbelt():
    scene, camera, target = common((1.0, 0.36, 0.1))
    steel = material("Brushed steel", (0.22, 0.32, 0.45), 0.82, 0.23)
    edge = material("Chrome", (0.72, 0.86, 0.93), 0.9, 0.2)
    strap = material("Safety orange belt", (0.96, 0.24, 0.055), 0.04, 0.73)
    lock = material("Lock signal", (1.0, 0.12, 0.045), 0.18, 0.24, 0.8)
    blue = material("Unlocked signal", (0.06, 0.62, 1.0), 0.1, 0.3, 0.6)
    box("Retractor backplate", (0, 0.58, 1.45), (2.45, 0.18, 2.7), steel, 0.12)
    for x in (-1.16, 1.16):
        box("Case side", (x, -0.06, 1.45), (0.12, 0.85, 2.7), edge, 0.06)
    box("Case bottom", (0, -0.06, 0.15), (2.45, 0.85, 0.12), edge, 0.045)
    bpy.ops.object.empty_add(location=(0, -0.2, 1.5))
    reel = bpy.context.object
    reel.name = "Rotating reel assembly"
    for x in (-0.6, 0.6):
        obj = cylinder("Ratchet disk", (x, -0.2, 1.5), 0.8, 0.18, edge, (0, math.pi / 2, 0), 40)
        obj.parent = reel
        for index in range(12):
            angle = index * math.tau / 12
            tooth = box("Visible ratchet tooth", (x, -0.2 + 0.76 * math.sin(angle), 1.5 + 0.76 * math.cos(angle)), (0.12, 0.11, 0.2), edge, 0.03)
            tooth.rotation_euler.x = -angle
            tooth.parent = reel
    axle = cylinder("Spool shaft", (0, -0.2, 1.5), 0.29, 1.45, steel, (0, math.pi / 2, 0))
    axle.parent = reel
    torus("Motion ring", (0.84, -0.2, 1.5), 1.04, 0.025, blue, (0, math.pi / 2, 0))
    box("Belt rising", (0, -0.42, 3.04), (0.5, 0.065, 0.75), strap, 0.025)
    box("Belt moving toward passenger", (0, -1.06, 3.75), (0.5, 1.2, 0.06), strap, 0.025)
    pawl = box("Pawl engages teeth", (0.84, -1.0, 2.44), (0.24, 0.47, 0.18), lock, 0.035)
    pawl.rotation_euler.x = math.radians(25)
    for frame, angle, pawl_z in ((1, 0, 2.44), (100, -0.95, 2.44), (165, -3.7, 2.22), (245, -3.76, 2.05), (400, -3.76, 2.05)):
        key(reel, frame, rotation=(angle, 0, 0))
        key(pawl, frame, location=(0.84, -1.0, pawl_z))
    key(camera, 1, location=(4.6, -9, 4.6)); key(camera, 145, location=(3.1, -7.2, 3.8)); key(camera, 400, location=(4.8, -8.3, 4.2))
    key(target, 1, location=(0, 0, 1.5)); key(target, 210, location=(0.3, -0.2, 1.75)); key(target, 400, location=(0.3, -0.2, 1.75))
    return scene


def train():
    scene, camera, target = common((0.06, 0.69, 1.0))
    rail = material("Rail alloy", (0.32, 0.41, 0.5), 0.83, 0.31)
    wheel = material("Wheel dark steel", (0.16, 0.24, 0.33), 0.9, 0.19)
    accent = material("Contact glow", (0.04, 0.75, 1.0), 0.05, 0.35, 1.0)
    warning = material("Correction glow", (1.0, 0.34, 0.08), 0.05, 0.35, 0.9)
    sleeper = material("Rail tie", (0.12, 0.16, 0.22), 0.25, 0.6)
    for x in (-1.15, 1.15):
        box("Rail web", (x, 0, 0.36), (0.11, 11.0, 0.68), rail, 0.035)
        box("Rail crown", (x, 0, 0.75), (0.23, 11.0, 0.12), rail, 0.04)
        box("Rail foot", (x, 0, 0.08), (0.32, 11.0, 0.09), rail, 0.02)
    for y in range(-5, 6):
        box("Sleeper", (0, y * 0.9, 0.05), (3.3, 0.3, 0.15), sleeper, 0.045)
    bpy.ops.object.empty_add(location=(0, 0, 1.42))
    bogie = bpy.context.object
    bogie.name = "Wheelset with shared axle"
    axle = cylinder("Axle", (0, 0, 1.42), 0.12, 2.7, rail, (0, math.pi / 2, 0))
    axle.parent = bogie
    axle.location = (0, 0, 0)
    for x, mat in ((-1.15, accent), (1.15, warning)):
        bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=0.64, radius2=0.69, depth=0.36, location=(x, 0, 1.42), rotation=(0, math.pi / 2, 0))
        conical = bpy.context.object
        conical.name = "Slightly tapered wheel tread"
        conical.data.materials.append(wheel)
        bevel = conical.modifiers.new("Tread highlights", "BEVEL")
        bevel.width = 0.035
        bevel.segments = 2
        conical.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
        conical.parent = bogie
        conical.location = (x, 0, 0)
        flange = cylinder("Inner flange", (x + (0.2 if x < 0 else -0.2), 0, 1.42), 0.77, 0.075, rail, (0, math.pi / 2, 0), 64)
        flange.parent = bogie
        flange.location = (x + (0.2 if x < 0 else -0.2), 0, 0)
        ring = torus("Contact indicator", (x, 0, 1.42), 0.66, 0.026, mat, (0, math.pi / 2, 0))
        ring.parent = bogie
        ring.location = (x, 0, 0)
    for frame, lateral, forward, roll in ((1, 0, -2.0, 0), (175, 0.25, -0.4, 0.25), (350, -0.2, 1.1, 1.0), (600, 0, 2.6, 2.2)):
        key(bogie, frame, location=(lateral, forward, 1.42), rotation=(roll, 0, 0))
    key(camera, 1, location=(4.3, -8.5, 4.0)); key(camera, 240, location=(3.2, -6.2, 3.2)); key(camera, 600, location=(4.5, -8.1, 4.3))
    key(target, 1, location=(0, 0, 1.2)); key(target, 600, location=(0, 0.4, 1.25))
    return scene


def escalator():
    scene, camera, target = common((0.12, 0.84, 1.0))
    camera.data.ortho_scale = 11.5
    aluminum = material("Escalator brushed aluminum", (0.24, 0.34, 0.45), 0.88, 0.32)
    groove = material("Deep tread grooves", (0.018, 0.035, 0.065), 0.15, 0.65)
    cyan = material("Moving step glow", (0.08, 0.78, 1.0), 0.1, 0.33, 1.0)
    orange = material("Comb safety teeth", (1.0, 0.39, 0.09), 0.45, 0.26, 0.8)
    box("Stationary landing", (0, 3.3, 0.62), (2.45, 1.0, 0.14), aluminum, 0.04)
    box("Comb plate edge", (0, 2.18, 0.78), (2.36, 0.16, 0.04), orange, 0.015)
    for i in range(17):
        x = -2.0 + i * 0.25
        box("Comb tooth", (x, 1.77, 0.76), (0.047, 0.42, 0.035), orange, 0.018)
    for index in range(4):
        bpy.ops.object.empty_add(location=(0, -4.5 + index * 1.7, 0.54))
        assembly = bpy.context.object
        assembly.name = f"Moving grooved step {index + 1}"
        body = box("Step tread", (0, 0, 0), (2.25, 0.72, 0.12), aluminum, 0.06)
        body.parent = assembly
        for rib_index in range(16):
            x = -1.95 + rib_index * 0.26
            rib = box("Longitudinal groove", (x, 0, 0.135), (0.04, 0.65, 0.015), groove, 0.005)
            rib.parent = assembly
        line = box("Step edge light", (0, -0.7, 0.13), (2.22, 0.02, 0.015), cyan, 0.008)
        line.parent = assembly
        first_y = -4.5 + index * 1.7
        key(assembly, 1, location=(0, first_y, 0.54))
        key(assembly, 500, location=(0, first_y + 5.3, 0.54))
    key(camera, 1, location=(5.0, -10.0, 7.0)); key(camera, 220, location=(3.5, -7.0, 5.4)); key(camera, 520, location=(4.5, -8.0, 6.2))
    key(target, 1, location=(0, -1.5, 0.6)); key(target, 520, location=(0, -0.4, 0.7))
    return scene


BUILDERS = {"seatbelt": seatbelt, "train": train, "escalator": escalator}


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    topic = args[0] if args else "seatbelt"
    if topic not in BUILDERS:
        raise SystemExit(f"unknown pilot: {topic}")
    OUT.mkdir(parents=True, exist_ok=True)
    scene = BUILDERS[topic]()
    scene.frame_end = {"seatbelt": 400, "train": 600, "escalator": 520}[topic]
    if "preview" in args:
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(OUT / f"{topic}-preview.png")
        scene.frame_set(150)
        bpy.ops.render.render(write_still=True)
        return
    if "sample" in args:
        scene.frame_end = 20
    frame_dir = OUT / f"{topic}-{'sample-' if 'sample' in args else ''}frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(frame_dir / "frame_")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / f"{topic}.blend"))
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()

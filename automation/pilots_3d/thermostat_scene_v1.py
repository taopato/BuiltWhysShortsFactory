"""First CPU-rendered thermostat visual proof; no publishing integration."""

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def material(name, color, metallic=0.0, roughness=0.35, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*color, 1)
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def cube(name, position, scale, mat, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("soft product edges", "BEVEL")
        mod.width = bevel
        mod.segments = 4
        obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    obj.data.materials.append(mat)
    return obj


def sphere(name, position, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=position)
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.shade_smooth()
    obj.data.materials.append(mat)
    return obj


def cylinder_between(name, start, end, radius, mat):
    start, end = Vector(start), Vector(end)
    middle = (start + end) / 2
    direction = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=direction.length, location=middle)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def label(words, location, size, mat):
    curve = bpy.data.curves.new(words, "FONT")
    curve.body = words
    curve.size = size
    curve.align_x = "CENTER"
    curve.extrude = 0.003
    obj = bpy.data.objects.new(words, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (math.pi / 2, 0, 0)
    obj.data.materials.append(mat)
    return obj


def aim(camera, target):
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--frame", type=int, default=1)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x = 720
    sc.render.resolution_y = 1280
    sc.render.resolution_percentage = 65
    sc.eevee.taa_render_samples = 16
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.render.film_transparent = False
    sc.world.color = (0.015, 0.027, 0.05)
    ink = material("deep blue", (0.015, 0.035, 0.065), 0.2)
    wall = material("wall cream", (0.52, 0.58, 0.62))
    white = material("porcelain white", (0.83, 0.88, 0.89), roughness=0.22)
    dark = material("glass display", (0.018, 0.04, 0.056), roughness=0.12)
    teal = material("signal teal", (0.06, 0.94, 0.84), emission=2.0)
    orange = material("heat orange", (1.0, 0.31, 0.07), emission=1.5)
    steel = material("brushed metal", (0.22, 0.32, 0.37), metallic=0.8)
    cube("studio wall", (0, 0.8, 2), (14, 0.2, 6), wall, 0.04)
    cube("stage", (0, 0, -0.15), (14, 3, 0.3), ink, 0.1)

    # Thermostat is deliberately a plausible wall-mounted product, not a human model.
    cube("thermostat body", (-4, -0.1, 2.7), (2.7, 0.42, 2.2), white, 0.23)
    cube("thermostat display", (-4, -0.34, 2.85), (2.18, 0.045, 1.35), dark, 0.09)
    label("18°", (-4, -0.38, 2.43), 0.7, teal)
    label("ROOM TEMP", (-4, -0.39, 3.3), 0.15, white)
    label("SET 22°", (-4, -0.35, 1.86), 0.22, dark)
    label("SENSES THE AIR", (-4, -0.48, 0.75), 0.33, dark)

    # Boiler housing: water connections and front control panel provide context.
    cube("boiler enclosure", (0, -0.03, 2.65), (2.35, 0.65, 3.1), white, 0.18)
    cube("boiler front panel", (0, -0.39, 2.6), (1.9, 0.045, 0.9), dark, 0.05)
    label("BOILER", (0, -0.45, 2.55), 0.32, white)
    for x in (-0.55, 0.55):
        cylinder_between("boiler pipe", (x, 0.03, 1.1), (x, 0.03, 0.4), 0.09, steel)
    label("CALL FOR HEAT", (0, -0.48, 0.75), 0.31, dark)

    # 3D radiator with separated fins, coherent plumbing, and hot-water glow.
    for index in range(9):
        x = 3.0 + index * 0.27
        cube(f"radiator fin {index}", (x, -0.16, 2.45), (0.19, 0.37, 2.3), white, 0.075)
    cylinder_between("radiator top", (2.9, -0.22, 3.44), (5.3, -0.22, 3.44), 0.08, steel)
    cylinder_between("radiator bottom", (2.9, -0.22, 1.45), (5.3, -0.22, 1.45), 0.08, steel)
    label("RADIATOR", (4.1, -0.5, 0.75), 0.32, dark)
    cylinder_between("hot supply", (0.55, 0.15, 0.4), (4.1, 0.15, 0.4), 0.08, orange)
    cylinder_between("radiator riser", (4.1, 0.15, 0.4), (4.1, 0.15, 1.4), 0.08, orange)
    cylinder_between("control signal", (-2.7, 0.1, 1.1), (-1.2, 0.1, 1.1), 0.035, teal)
    for x in (-2.25, -1.8):
        sphere("signal pulse", (x, -0.04, 1.1), 0.07, teal)

    bpy.ops.object.light_add(type="AREA", location=(-4, -5, 9))
    bpy.context.object.data.energy = 1100
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 6
    bpy.ops.object.light_add(type="AREA", location=(5, -2, 8))
    bpy.context.object.data.energy = 800
    bpy.context.object.data.size = 5
    bpy.ops.object.camera_add(location=(-4, -9, 4.5))
    camera = bpy.context.object
    aim(camera, (-4, 0, 2.2))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 5.8
    sc.camera = camera
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(args.out)
    sc.frame_set(args.frame)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()

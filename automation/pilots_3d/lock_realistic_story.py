"""More physically legible, original 3D pin-tumbler door-cylinder pilot.

This is an explanatory cutaway, not a dimensionally accurate lock or a guide
to bypassing one. It is deliberately isolated from the production publisher.
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
LAST = 480
SHEAR = 2.18
PIN_X = (-1.62, -0.82, 0, 0.82, 1.62)
PIN_LENGTHS = (0.51, 0.61, 0.48, 0.65, 0.55)


def metal(name, color, *, rough=0.27, metallic=0.9):
    mat = material(name, color, metallic, rough)
    nodes = mat.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 115
    noise.inputs["Detail"].default_value = 2
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.055
    bump.inputs["Distance"].default_value = 0.012
    mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return mat


def profile(name, outline, front_y, thickness, ink, bevel=0.0):
    """Extrude a flat X/Z silhouette; also used for the genuine-looking keyway."""
    count = len(outline)
    vertices = [(x, front_y, z) for x, z in outline]
    vertices += [(x, front_y + thickness, z) for x, z in outline]
    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, 2 * count))]
    for i in range(count):
        j = (i + 1) % count
        faces.append((i, j, j + count, i + count))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(ink)
    if bevel:
        mod = obj.modifiers.new("soft manufactured edges", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def half_tube(name, origin_x, length, center_z, inner, outer, ink):
    """Back half of a machined cylinder, leaving its working parts visible."""
    segments = 36
    verts = []
    for x in (origin_x - length / 2, origin_x + length / 2):
        for radius in (outer, inner):
            for i in range(segments + 1):
                a = -math.pi / 2 + math.pi * i / segments
                verts.append((x, radius * math.cos(a), center_z + radius * math.sin(a)))
    span = segments + 1
    faces = []
    for i in range(segments):
        faces += [
            (i, i + 1, 2 * span + i + 1, 2 * span + i),
            (span + i + 1, span + i, 3 * span + i, 3 * span + i + 1),
            (i, span + i, span + i + 1, i + 1),
            (2 * span + i + 1, 3 * span + i + 1, 3 * span + i, 2 * span + i),
        ]
    faces += [
        (0, 2 * span, 3 * span, span),
        (segments, span + segments, 3 * span + segments, 2 * span + segments),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(ink)
    bev = obj.modifiers.new("soft rim", "BEVEL")
    bev.width = 0.022
    bev.segments = 2
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")
    return obj


def spring(name, x, z0, z1, ink):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.013
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    n = 100
    spline.points.add(n - 1)
    for i, point in enumerate(spline.points):
        t = i / (n - 1)
        point.co = (x + 0.14 * math.cos(t * math.tau * 8), -0.19 + 0.14 * math.sin(t * math.tau * 8), z0 + t * (z1-z0), 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(ink)


def stage_light(origin_x, accent):
    for off, energy, color, size in (
        ((-3.4, -4.4, 6.2), 1050, (0.58, 0.76, 1.0), 4.0),
        ((3.8, 1.8, 5.0), 1650, accent, 3.8),
        ((1.0, -5.1, 2.7), 620, (1.0, 0.70, 0.44), 2.0),
    ):
        bpy.ops.object.light_add(type="AREA", location=(origin_x+off[0], off[1], off[2]))
        obj = bpy.context.object
        obj.data.energy = energy
        obj.data.shape = "DISK"
        obj.data.size = size
        obj.data.color = color
        point_camera(obj, (origin_x, 0, 1.65))


def key_silhouette(name, nickel, *, wrong=False):
    bpy.ops.object.empty_add(location=(0, 0, 0))
    root = bpy.context.object
    root.name = name
    offsets = (0.10, -0.13, 0.14, -0.11, 0.08) if wrong else (0, 0, 0, 0, 0)
    peaks = [SHEAR - PIN_LENGTHS[i] + offsets[i] for i in range(5)]
    top = [(-2.5, 1.49), (-2.18, 1.49)]
    for i, x in enumerate(PIN_X):
        top.extend(((x - 0.19, peaks[i]), (x + 0.19, peaks[i])))
    top.extend(((2.42, 1.44), (2.55, 1.36)))
    outline = [(-2.55, 1.12), (2.55, 1.12)] + list(reversed(top))
    blade = profile(name+" / cut metal blade", outline, -0.42, 0.22, nickel, 0.025)
    blade.parent = root
    # The bow and shoulder make the silhouette unmistakably a real key.
    bow = torus(name+" / oval key bow", (-3.20, -0.32, 1.55), 0.50, 0.105, nickel, (math.pi/2, 0, 0))
    bow.scale.x = 1.27
    bow.parent = root
    collar = box(name+" / shoulder", (-2.57, -0.32, 1.46), (0.22, 0.26, 0.75), nickel, 0.045)
    collar.parent = root
    for sx in (-2.42, -1.08, 0.38, 1.85):
        groove = box(name+" / side milling", (sx, -0.49, 1.28), (0.62, 0.018, 0.025), nickel, 0.01)
        groove.parent = root
    return root


def front_lock(origin, door, chrome, nickel, black, brass, *, turn=False):
    stage_light(origin, (0.96, 0.56, 0.20))
    box("Solid door, not a floating prop", (origin, 0.85, 1.65), (6.2, 0.42, 3.8), door, 0.07)
    cylinder("Dark gasket behind escutcheon", (origin, 0.55, 1.65), 1.06, 0.065, black, (math.pi/2,0,0), 96)
    cylinder("Machined exterior escutcheon", (origin, 0.42, 1.65), 1.00, 0.19, chrome, (math.pi/2,0,0), 96)
    rotating = None
    if turn:
        bpy.ops.object.empty_add(location=(origin, 0.0, 1.65))
        rotating = bpy.context.object
        rotating.name = "Cylinder plug rotates only after correct key"
    face = cylinder("Brass cylinder plug face", (origin, 0.19, 1.65), 0.72, 0.13, brass, (math.pi/2,0,0), 96)
    keyhole = profile("Paracentric-style keyway opening", [
        (origin-0.11, 2.10), (origin+0.11, 2.10), (origin+0.11, 1.87),
        (origin+0.26, 1.78), (origin+0.20, 1.64), (origin+0.08, 1.63),
        (origin+0.13, 1.48), (origin+0.08, 1.19), (origin-0.16, 1.19),
        (origin-0.12, 1.49), (origin-0.24, 1.55), (origin-0.20, 1.70),
        (origin-0.11, 1.77),
    ], 0.10, 0.045, black, 0.012)
    if rotating:
        face.parent = rotating
        face.location = (0, 0.19, 0)
        keyhole.parent = rotating
        # The polygon vertices were authored in stage coordinates. Remove the
        # parent's stage offset so the opening stays on the rotating plug.
        keyhole.location.x = -origin
        keyhole.location.z = -1.65
        for frame, angle in ((348,0),(366,0),(415,-math.pi/3),(425,-math.pi/3)):
            key(rotating, frame, rotation=(0, angle, 0))
    for xoff in (-0.85, 0.85):
        cylinder("Escutcheon mounting screw", (origin+xoff, 0.30, 1.65), 0.055, 0.015, nickel, (math.pi/2,0,0), 24)


def cutaway(origin, steel, satin, brass, black, spring_ink, signal, *, wrong, start, inserted):
    stage_light(origin, (0.98,0.49,0.22) if wrong else (0.22,0.73,0.90))
    box("Cutaway display plinth",(origin,0,0.10),(7.4,4.6,0.15),black,0.08)
    box("Solid rear lock body",(origin,0.91,1.76),(6.14,0.18,2.84),steel,0.08)
    box("Top of cylinder housing",(origin,0.37,3.18),(6.14,1.16,0.14),steel,0.05)
    half_tube("Outer steel cylinder cut in half", origin, 6.2, 1.53, 1.03, 1.18, steel)
    half_tube("Rotating brass plug, cut in half", origin, 5.75, 1.53, 0.72, 0.82, brass)
    for edge_x in (origin-2.99, origin+2.99):
        torus("Precision-machined end ring", (edge_x,0,1.53), 0.98, 0.055, satin, (0,math.pi/2,0))
    # A dark keyway recess and metal plug lips make the cross section read as a
    # cylinder, not a row of free-floating pins.
    box("Dark keyway channel", (origin,-0.12,1.06), (5.5,0.45,0.12), black, 0.04)
    for z in (0.81, 2.25):
        box("Polished plug cut edge", (origin,-0.08,z), (5.65,0.18,0.055), satin, 0.022)
    bar = box("Shear line indicator", (origin,-0.60,SHEAR), (5.65,0.028,0.026), signal, 0.008)
    key(bar, start, scale=(0.01,1,1))
    key(bar, inserted, scale=(1,1,1))
    blade = key_silhouette("Wrong key" if wrong else "Matching key", satin, wrong=wrong)
    key(blade,start,location=(origin-6.6,0,0))
    key(blade,inserted,location=(origin,0,0))
    lengths = PIN_LENGTHS
    mismatch = (0.10,-0.13,0.14,-0.11,0.08) if wrong else (0,0,0,0,0)
    for i, local_x in enumerate(PIN_X):
        x = origin + local_x
        before = SHEAR-0.16
        after = SHEAR + mismatch[i]
        lower = cylinder(f"Key pin {i+1}",(x,-0.16,before-lengths[i]/2),0.16,lengths[i],brass,vertices=40)
        driver = cylinder(f"Driver pin {i+1}",(x,-0.16,before+0.21),0.16,0.42,satin,vertices=40)
        for part, z_at_start, z_at_finish in (
            (lower,before-lengths[i]/2,after-lengths[i]/2),
            (driver,before+0.21,after+0.21),
        ):
            key(part,start,location=(x,-0.16,z_at_start))
            key(part,start+int((inserted-start)*(i+1)/6),location=(x,-0.16,z_at_finish))
        torus("Pin chamber rim",(x,-0.16,2.62),0.22,0.045,steel)
        spring(f"Steel coil spring {i+1}",x,2.63,3.03,spring_ink)
        cylinder("Chamber cap",(x,-0.16,3.08),0.20,0.08,steel,vertices=40)


def bolt_stage(origin, steel, satin, brass, door, black):
    stage_light(origin, (0.99,0.55,0.24))
    box("Lock case",(origin,0.55,1.53),(6.6,0.26,2.5),black,0.12)
    # A round cylinder tailpiece rotates a cam, which moves a separate latch.
    cylinder("Tailpiece shaft",(origin-1.55,-0.16,1.55),0.18,2.3,satin,(0,math.pi/2,0),64)
    cam = cylinder("Cam disk",(origin-0.45,-0.68,1.55),0.65,0.20,brass,(math.pi/2,0,0),80)
    bpy.ops.object.empty_add(location=(origin-0.45,-0.86,1.55))
    cam_root = bpy.context.object
    cam_root.name = "Cam rotates and retracts bolt"
    tooth = box("Offset cam lobe",(0.48,-0.05,0),(0.68,0.18,0.24),brass,0.07)
    tooth.parent = cam_root
    for f,a in ((416,0),(455,-math.pi/2),(480,-math.pi/2)):
        key(cam_root,f,rotation=(0,a,0))
    receiver = box("Door-frame strike plate",(origin+2.45,0,1.55),(0.22,1.1,1.3),satin,0.06)
    box("Door jamb behind plate",(origin+2.85,0.46,1.55),(0.65,1.2,2.4),door,0.09)
    bolt = cylinder("Sliding steel bolt",(origin+1.20,-0.05,1.55),0.35,2.12,steel,(0,math.pi/2,0),64)
    key(bolt,416,location=(origin+1.20,-0.05,1.55))
    key(bolt,468,location=(origin+0.30,-0.05,1.55))
    key(bolt,480,location=(origin+0.30,-0.05,1.55))


def shot(camera,target,start,end,p0,p1,look0,look1,scale0,scale1):
    key(camera,start,location=p0)
    key(camera,end,location=p1)
    key(target,start,location=look0)
    key(target,end,location=look1)
    camera.data.ortho_scale=scale0
    camera.data.keyframe_insert("ortho_scale",frame=start)
    camera.data.ortho_scale=scale1
    camera.data.keyframe_insert("ortho_scale",frame=end)


def build():
    scene,camera,target=common((0.95,0.46,0.16))
    scene.render.resolution_x=480
    scene.render.resolution_y=854
    scene.render.fps=FPS
    scene.frame_end=LAST
    steel=metal("Machined nickel steel",(0.43,0.52,0.59),rough=0.22)
    satin=metal("Satin key and springs",(0.75,0.80,0.82),rough=0.29)
    brass=metal("Warm machined brass",(0.72,0.43,0.16),rough=0.23)
    door=material("Dark painted door",(0.006,0.010,0.016),0.0,0.65)
    grain=door.node_tree.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value=8
    grain.inputs["Detail"].default_value=3
    relief=door.node_tree.nodes.new("ShaderNodeBump")
    relief.inputs["Strength"].default_value=0.10
    relief.inputs["Distance"].default_value=0.025
    door.node_tree.links.new(grain.outputs["Fac"],relief.inputs["Height"])
    door.node_tree.links.new(relief.outputs["Normal"],door.node_tree.nodes.get("Principled BSDF").inputs["Normal"])
    black=material("Real keyway shadow",(0.004,0.006,0.010),0.0,0.93)
    red=material("Blocked line red",(0.92,0.06,0.04),0.2,0.24,0.85)
    cyan=material("Clear line cyan",(0.04,0.73,0.84),0.2,0.24,0.85)
    front_lock(0,door,steel,satin,black,brass)
    cutaway(13,steel,satin,brass,black,satin,red,wrong=True,start=56,inserted=137)
    cutaway(28,steel,satin,brass,black,satin,cyan,wrong=False,start=138,inserted=310)
    front_lock(42,door,steel,satin,black,brass,turn=True)
    bolt_stage(55,steel,satin,brass,door,black)
    for args in [
        (1,55,(0.0,-8.2,4.3),(0.5,-6.4,3.5),(0,0,1.65),(0,0,1.65),5.2,4.0),
        (56,102,(16,-9.0,5.2),(14.5,-7.7,4.3),(13,0,1.7),(13,0,1.7),11.5,9.5),
        (103,137,(10.4,-6.5,3.8),(14.5,-5.5,3.6),(13,0,1.9),(13,0,1.9),4.6,4.1),
        (138,205,(31,-9.0,5.0),(29.0,-7.7,4.3),(28,0,1.7),(28,0,1.7),11.5,9.5),
        (206,279,(25.8,-6.0,3.7),(28.7,-5.5,3.5),(28,0,2.05),(28,0,2.05),4.6,3.9),
        (280,347,(29.5,-6.3,3.7),(27.0,-5.4,3.5),(28,0,2.05),(28,0,2.05),4.0,3.8),
        (348,415,(42.5,-7.6,4.1),(40.8,-5.9,3.5),(42,0,1.65),(42,0,1.65),5.1,4.0),
        (416,480,(57.5,-8.7,4.8),(55.7,-7.6,4.2),(55,0,1.55),(55,0,1.55),8.5,7.8),
    ]:
        shot(camera,target,*args)
    return scene


def main():
    args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    mode=args[0] if args else "preview"
    if mode not in {"preview","render"}:
        raise SystemExit("preview [frames...] or render")
    OUT.mkdir(parents=True,exist_ok=True)
    scene=build()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"lock-realistic.blend"))
    if mode=="preview":
        for frame in map(int,args[1:] or [1,100,250,350,450]):
            scene.frame_set(frame)
            scene.render.filepath=str(OUT/f"lock-realistic-preview-{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
    else:
        frames=OUT/"lock-realistic-frames"
        frames.mkdir(exist_ok=True)
        for frame in range(1,LAST+1):
            output=frames/f"frame_{frame:04d}.png"
            if output.is_file():
                continue
            scene.frame_set(frame)
            scene.render.filepath=str(output)
            bpy.ops.render.render(write_still=True)


if __name__=="__main__":
    main()

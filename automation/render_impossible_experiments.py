from __future__ import annotations

import math
import os
import random
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "pilots" / "impossible-experiments"
FPS, FRAMES = 24, 240


def clear() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.materials, bpy.data.curves, bpy.data.meshes, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def mat(name: str, color: tuple[float, float, float, float], metallic=0.0, rough=.35,
        transmission=0.0, emission=None, strength=0.0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Transmission Weight"].default_value = transmission
    bsdf.inputs["Alpha"].default_value = color[3]
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    if color[3] < 1:
        material.surface_render_method = "DITHERED"
    return material


def cube(name, loc, scale, material, bevel=.12):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object; obj.name = name; obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Soft edges", "BEVEL"); mod.width = bevel; mod.segments = 3
    obj.data.materials.append(material)
    return obj


def sphere(name, loc, radius, material, ico=False):
    if ico:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=radius, location=loc)
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=radius, location=loc)
    obj = bpy.context.object; obj.name = name; obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return obj


def cylinder(name, loc, radius, depth, material, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object; obj.name = name; obj.data.materials.append(material)
    bevel = obj.modifiers.new("Edge", "BEVEL"); bevel.width=.08; bevel.segments=3
    bpy.ops.object.shade_smooth()
    return obj


def key(obj, frame, location=None, scale=None, rotation=None, hide=None):
    if location is not None: obj.location = location; obj.keyframe_insert("location", frame=frame)
    if scale is not None: obj.scale = scale; obj.keyframe_insert("scale", frame=frame)
    if rotation is not None: obj.rotation_euler = rotation; obj.keyframe_insert("rotation_euler", frame=frame)
    if hide is not None:
        obj.hide_render = hide; obj.keyframe_insert("hide_render", frame=frame)


def setup_scene(accent=(.15, .75, 1.0, 1)):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 360; scene.render.resolution_y = 640; scene.render.resolution_percentage = 100
    scene.render.fps = FPS; scene.frame_start = 1; scene.frame_end = FRAMES
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"; scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"; scene.render.ffmpeg.ffmpeg_preset = "REALTIME"
    scene.render.film_transparent = False
    scene.world.color = (.005, .008, .015)
    world = scene.world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (.005, .008, .018, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = .18
    dark = mat("Floor", (.018, .025, .045, 1), metallic=.25, rough=.25)
    cube("Floor", (0,0,-.3), (4.8,4.8,.25), dark, .18)
    bpy.ops.object.light_add(type="AREA", location=(3,-4,7)); keylight=bpy.context.object
    keylight.data.energy=1150; keylight.data.shape="DISK"; keylight.data.size=5
    keylight.data.color=(.62,.78,1.0); keylight.rotation_euler=(math.radians(23),0,math.radians(38))
    bpy.ops.object.light_add(type="AREA", location=(-4,1,4)); fill=bpy.context.object
    fill.data.energy=900; fill.data.size=4; fill.data.color=accent[:3]
    bpy.ops.object.light_add(type="POINT", location=(0,2,5)); bpy.context.object.data.energy=550
    bpy.ops.object.empty_add(location=(0,0,1.6)); target=bpy.context.object
    bpy.ops.object.camera_add(location=(0,-10,4.2)); camera=bpy.context.object
    camera.data.lens=54; scene.camera=camera
    constraint=camera.constraints.new(type="TRACK_TO"); constraint.target=target
    constraint.track_axis="TRACK_NEGATIVE_Z"; constraint.up_axis="UP_Y"
    key(camera,1,(0,-10,4.2)); key(camera,90,(.55,-8.6,3.4)); key(camera,240,(0,-9.4,3.8))
    return scene, target


def press(material):
    for x in (-2.2,2.2): cube("PressColumn",(x,0,2.8),(.25,.5,3.0),material,.08)
    cube("PressTop",(0,0,5.7),(2.55,.72,.35),material,.12)
    cylinder("Ram",(0,0,4.65),.48,1.8,material)
    return cylinder("PressPlate",(0,0,3.75),1.65,.35,material)


def press_core():
    scene,_=setup_scene((.1,.65,1,1))
    steel=mat("Steel",(.16,.2,.27,1),.9,.18); gold=mat("Core",(.95,.38,.06,1),.8,.16,emission=(1,.12,.01),strength=.35)
    # Opaque ceramic shell keeps the glowing core genuinely hidden until impact.
    glass=mat("Shell",(.025,.32,.82,1),.35,.16)
    plate=press(steel); shell=sphere("GlassShell",(0,0,1.25),1.25,glass); core=sphere("HiddenCore",(0,0,1.25),.55,gold,True)
    key(plate,1,(0,0,3.75)); key(plate,100,(0,0,2.45)); key(plate,145,(0,0,1.72)); key(plate,190,(0,0,2.65)); key(plate,240,(0,0,3.75))
    key(shell,1,scale=(1,1,1),hide=False); key(shell,100,scale=(1,1,.78)); key(shell,124,scale=(1.12,1.12,.42)); key(shell,127,hide=True)
    key(core,1,scale=(1,1,1)); key(core,125,scale=(1.05,1.05,.72)); key(core,165,scale=(1.05,1.05,.72)); key(core,210,scale=(1,1,.92))
    rng=random.Random(8)
    for i in range(18):
        shard=sphere(f"Shard{i}",(0,0,1.25),.18,glass,True); shard.scale=(.1,.1,.1); shard.hide_render=True
        key(shard,124,hide=True); key(shard,126,hide=False,scale=(.1,.1,.1))
        angle=2*math.pi*i/18; target=(2.4*math.cos(angle),2.4*math.sin(angle),rng.uniform(.2,3.2))
        key(shard,165,location=target,scale=(rng.uniform(.3,.8),)*3,rotation=(rng.random()*4,rng.random()*4,rng.random()*4))
    return scene


def hidden_cut():
    scene,_=setup_scene((.75,.18,1,1))
    metal=mat("Blade",(.35,.4,.5,1),.95,.12); crystal=mat("Crystal",(.8,.05,1,1),.35,.12,emission=(.7,.02,1),strength=4)
    shell=mat("Block",(.12,.5,.75,1),.15,.22)
    left=cube("LeftHalf",(-.76,0,1.2),(.74,1.25,1.25),shell,.22); right=cube("RightHalf",(.76,0,1.2),(.74,1.25,1.25),shell,.22)
    gem=sphere("MysteryCrystal",(0,0,1.2),.68,crystal,True); key(gem,1,scale=(.05,.05,.05)); key(gem,130,scale=(.05,.05,.05)); key(gem,165,scale=(1,1,1))
    blade=cube("Knife",(0,0,5.2),(.08,1.8,1.2),metal,.03); blade.rotation_euler[1]=math.radians(-8)
    key(blade,1,(0,0,5.2)); key(blade,115,(0,0,.35)); key(blade,165,(0,0,.1)); key(blade,220,(0,0,4.8))
    key(left,1,(-.76,0,1.2)); key(right,1,(.76,0,1.2)); key(left,125,(-.76,0,1.2)); key(right,125,(.76,0,1.2))
    key(left,175,(-2.05,0,1.05),rotation=(0,math.radians(-14),math.radians(8))); key(right,175,(2.05,0,1.05),rotation=(0,math.radians(14),math.radians(-8)))
    return scene


def spring_crush():
    scene,_=setup_scene((.1,1,.45,1)); steel=mat("Steel",(.15,.18,.25,1),.9,.16); plate=press(steel)
    colors=[(.85,.12,.08,1),(.95,.48,.05,1),(.95,.82,.08,1)]
    layers=[]
    for i,c in enumerate(colors): layers.append(cylinder(f"SoftLayer{i}",(0,0,.25+i*.62),1.25,.55,mat(f"Layer{i}",c,.25,.22)))
    green=mat("Spring",(.05,.95,.32,1),.65,.18,emission=(.02,.5,.08),strength=.6)
    rings=[]
    for i in range(5):
        bpy.ops.mesh.primitive_torus_add(major_radius=.8,minor_radius=.12,major_segments=48,minor_segments=12,location=(0,0,2.05+i*.28))
        rings.append(bpy.context.object); rings[-1].data.materials.append(green)
    key(plate,1,(0,0,4.0)); key(plate,130,(0,0,1.0)); key(plate,150,(0,0,.75)); key(plate,175,(0,0,3.4)); key(plate,240,(0,0,4.0))
    for i,obj in enumerate(layers): key(obj,1,scale=(1,1,1)); key(obj,80+i*15,scale=(1,1,1)); key(obj,120+i*10,scale=(1.16,1.16,.18))
    for i,obj in enumerate(rings): key(obj,1,scale=(1,1,1)); key(obj,140,scale=(1,1,.45)); key(obj,172,scale=(1.05,1.05,1.6)); key(obj,220,scale=(1,1,1))
    return scene


def chain_rescue():
    scene,_=setup_scene((1,.42,.08,1)); white=mat("Ivory",(.8,.86,.95,1),.15,.25); gold=mat("Prize",(1,.35,.03,1),.8,.14,emission=(1,.08,.01),strength=.6)
    dominos=[]
    for i in range(12):
        x=-2.6+i*.47; y=.25*math.sin(i*.65)
        d=cube(f"Domino{i}",(x,y,.55),(.12,.28,.55),white,.05); dominos.append(d)
        key(d,1,rotation=(0,0,0)); key(d,28+i*8,rotation=(0,0,0)); key(d,39+i*8,rotation=(0,math.radians(76),0))
    beam=cube("Lever",(2.65,0,.72),(1.15,.18,.12),gold,.08); key(beam,1,rotation=(0,0,0)); key(beam,136,rotation=(0,0,0)); key(beam,160,rotation=(0,math.radians(-24),0))
    ball=sphere("RescuedBall",(3.35,0,1.2),.48,gold); key(ball,1,(3.35,0,1.2)); key(ball,150,(3.35,0,1.2)); key(ball,185,(1.5,0,.35)); key(ball,220,(0,0,.55))
    # Glowing target ring.
    bpy.ops.mesh.primitive_torus_add(major_radius=.7,minor_radius=.1,location=(0,0,.05)); bpy.context.object.data.materials.append(gold)
    return scene


def balloon_surprise():
    scene,_=setup_scene((1,.08,.3,1)); red=mat("Balloon",(.95,.025,.08,1),.12,.16); steel=mat("Needle",(.45,.5,.62,1),.95,.1)
    balloon=sphere("Balloon",(0,0,1.55),1.45,red); key(balloon,1,scale=(1,1,1)); key(balloon,120,scale=(1,1,1)); key(balloon,155,scale=(.82,1.05,1.04)); key(balloon,205,scale=(1,1,1))
    shaft=cylinder("Needle",(-4.1,0,1.55),.11,4.0,steel,rotation=(0,math.radians(90),0)); tip=cylinder("Tip",(-1.98,0,1.55),.18,.65,steel,rotation=(0,math.radians(90),0)); tip.scale=(1,1,.08)
    key(shaft,1,(-4.1,0,1.55)); key(tip,1,(-1.98,0,1.55)); key(shaft,130,(-2.1,0,1.55)); key(tip,130,(.02,0,1.55))
    key(shaft,155,(-1.85,0,1.55),rotation=(0,math.radians(90),0)); key(tip,155,(.27,0,1.55),rotation=(0,math.radians(90),0))
    key(tip,180,(.17,0,1.25),rotation=(0,math.radians(125),0)); key(shaft,205,(-3.2,0,1.55))
    return scene


def audio(path: Path, reveal=6.4):
    rate=44100; duration=FRAMES/FPS; rng=random.Random(path.name)
    with wave.open(str(path),"wb") as out:
        out.setparams((2,2,rate,int(duration*rate),"NONE","not compressed")); noise=0.0
        for i in range(int(duration*rate)):
            t=i/rate; noise=noise*.94+rng.uniform(-1,1)*.06
            v=.016*math.sin(2*math.pi*(48+t*7)*t)+.012*noise
            d=t-reveal
            if 0<=d<.35: v+=.22*(1-d/.35)*math.sin(2*math.pi*(130-d*220)*d)
            d=t-(reveal+.45)
            if 0<=d<1.2: v+=.09*(1-d/1.2)*math.sin(2*math.pi*(620+d*180)*d)
            n=int(max(-1,min(1,v))*32767); out.writeframesraw(struct.pack("<hh",n,n))


def render(name: str, builder) -> Path:
    clear(); scene=builder(); OUT.mkdir(parents=True,exist_ok=True)
    silent=OUT/f"{name}-silent.mp4"; scene.render.filepath=str(silent)
    for action in bpy.data.actions:
        for fc in action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation="BEZIER"
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/f"{name}.blend"))
    bpy.ops.render.render(animation=True)
    wav=OUT/f"{name}.wav"; audio(wav)
    final=OUT/f"{name}.mp4"; ffmpeg=shutil.which("ffmpeg") or "ffmpeg"
    subprocess.run([ffmpeg,"-hide_banner","-loglevel","error","-y","-i",str(silent),"-i",str(wav),
        "-vf","scale=1080:1920:flags=lanczos,drawtext=text='BW':x=55:y=55:fontsize=42:fontcolor=white@0.65:box=1:boxcolor=black@0.25:boxborderw=13",
        "-c:v","libx264","-preset","fast","-crf","18","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(final)],check=True)
    print(final,flush=True); return final


def main():
    builders=[("01-hidden-core-press",press_core),("02-mystery-cut",hidden_cut),("03-spring-vs-press",spring_crush),("04-domino-rescue",chain_rescue),("05-needle-vs-balloon",balloon_surprise)]
    requested=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    for name,builder in builders:
        if not requested or name in requested: render(name,builder)


if __name__=="__main__": main()

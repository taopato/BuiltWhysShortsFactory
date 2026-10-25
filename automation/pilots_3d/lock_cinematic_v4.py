"""Review-only cinematic pin-tumbler deadbolt pilot.

One door, one cylinder and one continuous mechanical timeline. No upload path.
The human is a CC0 MakeHuman export; see the pilot's asset manifest.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_pilot import box, cylinder, material, point_camera, torus

ROOT = Path(__file__).resolve().parents[2]
OUT = Path("D:/CreatorLab/ShortsFactory/pilots/lock-v4")
ASSET = Path("D:/CreatorLab/ShortsFactory/assets/3d/ara-human/Athletic_man.glb")
FPS = 24
SECONDS = 36
END = FPS * SECONDS
LOCK_X = 0.56
LOCK_Z = 1.35
SHEAR_Z = 1.607
PIN_Y = (0.23, 0.46, 0.69, 0.92, 1.15)
PIN_HEIGHT = (0.165, 0.215, 0.18, 0.235, 0.19)


def f(sec: float) -> int:
    return 1 + round(FPS * sec)


def animate(obj, frame, *, loc=None, rot=None, scale=None):
    if loc is not None:
        if obj.parent:
            parent_transform=obj.parent.matrix_world @ obj.matrix_parent_inverse
            obj.location=parent_transform.inverted() @ Vector(loc)
        else:
            obj.location=loc
        obj.keyframe_insert(data_path="location", frame=frame)
    if rot is not None:
        obj.rotation_euler = rot
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert(data_path="scale", frame=frame)


def reset():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 1280
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = END
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "AgX"
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.025, 0.035, 0.055, 1)
    bg.inputs["Strength"].default_value = 0.48
    return scene


def mat(name, rgb, metallic=0, rough=0.5):
    return material(name, rgb, metallic, rough)


def put_on_hinge(obj, hinge):
    old = obj.matrix_world.copy()
    obj.parent = hinge
    obj.matrix_world = old
    return obj


def empt(name, loc=(0, 0, 0)):
    bpy.ops.object.empty_add(location=loc)
    bpy.context.object.name = name
    return bpy.context.object


def area(name, pos, power, color, size, target):
    bpy.ops.object.light_add(type="AREA", location=pos)
    obj = bpy.context.object
    obj.name = name
    obj.data.energy = power
    obj.data.color = color
    obj.data.shape = "DISK"
    obj.data.size = size
    point_camera(obj, target)
    return obj


def door_set(wood, frame_mat, floor_mat, wall, steel, brass, dark):
    warm_wall=mat("Warm room visible through open door",(.32,.22,.15),0,.77)
    box("Hall concrete floor", (0, -1.5, -0.09), (8, 11, 0.16), floor_mat, .035)
    box("Interior floor", (0, 2.7, -0.08), (8, 5, .16), floor_mat, .035)
    box("Warm interior back wall", (0, 3.85, 1.54), (2.48, .12, 3.1), warm_wall, .015)
    box("Wall left of door", (-2.45, .12, 1.55), (2.55, .22, 3.4), wall, .035)
    box("Wall right of door", (2.46, .12, 1.55), (2.5, .22, 3.4), wall, .035)
    box("Wall over door", (0, .12, 3.35), (2.55, .22, .48), wall, .03)
    for x in (-1.21, 1.21):
        box("Door frame vertical", (x, -.17, 1.56), (.12, .27, 3.16), frame_mat, .025)
    box("Door frame header", (0, -.17, 3.18), (2.56, .27, .12), frame_mat, .025)
    hinge = empt("Door hinge - whole lock moves with the door", (-1.15, 0, 0))
    door = put_on_hinge(box("Single real door slab", (0, 0, 1.53), (2.28, .17, 3.05), wood, .04), hinge)
    # Panel millwork creates a familiar everyday front door, not a studio prop.
    for z, h in ((2.31, .75), (1.25, 1.02), (.42, .48)):
        put_on_hinge(box("Raised door panel", (-.04, -.105, z), (1.78, .04, h), wood, .022), hinge)
    for x in (-.94, .87):
        put_on_hinge(box("Door stile highlight", (x, -.133, 1.52), (.024, .018, 2.7), frame_mat, .008), hinge)
    # Handles on the same door, below the cylinder.
    for y in (-.25, .25):
        put_on_hinge(cylinder("Handle round rosette", (.56, y, .93), .13, .05, steel, (math.pi/2, 0, 0), 64), hinge)
        put_on_hinge(cylinder("Handle spindle", (.56, y-(.055 if y<0 else -.055), .93), .047, .15, dark, (math.pi/2, 0, 0)), hinge)
        put_on_hinge(box("Lever handle", (.79, y-(.12 if y<0 else -.12), .93), (.45, .07, .065), steel, .025), hinge)
    plate = put_on_hinge(cylinder("Escutcheon black gasket", (LOCK_X, -.22, LOCK_Z), .205, .027, dark, (math.pi/2, 0, 0), 80), hinge)
    put_on_hinge(cylinder("Brushed metal escutcheon", (LOCK_X, -.25, LOCK_Z), .19, .046, steel, (math.pi/2,0,0),80), hinge)
    plug_face = cylinder("Brass plug face", (LOCK_X,-.291,LOCK_Z), .137, .04, brass,(math.pi/2,0,0),80)
    cutters=(box("Keyway rectangular drill",(LOCK_X,-.293,LOCK_Z-.012),(.023,.16,.055),dark),
             cylinder("Keyway round drill",(LOCK_X,-.293,LOCK_Z+.018),.023,.16,dark,(math.pi/2,0,0),48))
    for cutter in cutters:
        bpy.context.view_layer.objects.active=plug_face
        boolean=plug_face.modifiers.new("Real recessed keyway","BOOLEAN")
        boolean.operation="DIFFERENCE"
        boolean.object=cutter
        bpy.ops.object.modifier_apply(modifier=boolean.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
    put_on_hinge(plug_face,hinge)
    keyhole=put_on_hinge(cylinder("Black inner keyway",(LOCK_X,-.294,LOCK_Z),.075,.008,dark,(math.pi/2,0,0),48),hinge)
    for x in (LOCK_X-.153, LOCK_X+.153):
        put_on_hinge(cylinder("Escutcheon screw", (x,-.286,LOCK_Z), .012,.008,steel,(math.pi/2,0,0),20),hinge)
    # Exterior hardware is modeled at real-world scale. The subsequent
    # cutaway is an intentionally magnified explanatory view of this lock.
    hardware=put_on_hinge(empt("Exterior key cylinder actual scale",(LOCK_X,0,LOCK_Z)),hinge)
    handles=put_on_hinge(empt("Exterior handle actual scale",(LOCK_X,0,.93)),hinge)
    for obj in list(hinge.children):
        if obj.name.startswith(("Escutcheon","Brushed metal escutcheon",
                                "Brass plug face","Black inner keyway")):
            old=obj.matrix_world.copy(); obj.parent=hardware; obj.matrix_world=old
        elif obj.name.startswith(("Handle round rosette","Handle spindle","Lever handle")):
            old=obj.matrix_world.copy(); obj.parent=handles; obj.matrix_world=old
    hardware.scale=(.38,.6,.38)
    handles.scale=(.62,1,.62)
    # Subtle hallway details remain coherent during camera orbit.
    box("Wall baseboard left", (-2.42, -.07, .1), (2.4,.09,.16), frame_mat,.015)
    box("Wall baseboard right", (2.44, -.07, .1), (2.45,.09,.16), frame_mat,.015)
    box("Warm hallway lamp fixture", (2.5,-.32,2.55), (.44,.16,.12), brass,.025)
    area("Warm practical", (2.3,-1.0,2.75), 420, (1,.71,.43), 1.2, (.4,0,1.5))
    for frame, angle in ((f(0),0),(f(30.5),0),(f(34.4),-.78),(END,-1.0)):
        animate(hinge,frame,rot=(0,0,angle))
    hinge.rotation_euler=(0,0,0)
    return hinge, door, plug_face, keyhole


def actor(glove, coat):
    if not ASSET.exists():
        raise FileNotFoundError(f"Licensed actor asset missing: {ASSET}")
    previous = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(ASSET))
    imported = set(bpy.data.objects)-previous
    root = empt("Realistic CC0 MakeHuman character at door")
    for obj in imported:
        if obj.parent is None:
            old=obj.matrix_world.copy()
            obj.parent=root
            obj.matrix_world=old
    root.location = (-.68,-2.2,0)
    root.scale = (1.1,1.1,1.1)
    root.rotation_euler.z = math.pi
    # Keep the person legible in a short establishing shot, but avoid a face
    # close-up: the explanatory film is about the hand/key/lock.
    for frame, loc in ((f(0),(-.68,-2.2,0)),(f(3.5),(-.05,-.85,0)),
                       (f(29.5),(-.05,-.85,0)),(f(32),(-.52,-1.3,0)),
                       (END,(-.73,-1.65,0))):
        animate(root,frame,loc=loc)
    rig=next(obj for obj in imported if obj.type=="ARMATURE")
    hand_target=empt("Right hand follows the key bow",(-.39,-2.06,1.03))
    ik=rig.pose.bones["RightHand"].constraints.new("IK")
    ik.target=hand_target
    ik.chain_count=3
    ik.use_rotation=False
    for t,loc in ((0,(-.39,-2.06,1.03)),(2.2,(.24,-1.15,1.08)),
                  (3.5,(LOCK_X,-1.0,LOCK_Z)),(6.2,(LOCK_X,-.65,LOCK_Z)),
                  (9.4,(LOCK_X,-.34,LOCK_Z)),(29.5,(LOCK_X,-.34,LOCK_Z)),
                  (31.5,(-.22,-1.25,1.24)),(35,(-.48,-1.56,1.03))):
        animate(hand_target,f(t),loc=loc)
    return root


def key_mesh(glove, nickel, bow_mat, coat):
    # Coordinate system: blade advances in +Y; its five cut heights are
    # defined in the same function that drives the pins below.
    carrier = empt("Correct key plus visible hand")
    mesh = bpy.data.meshes.new("Cut key blade mesh")
    y_top = (-.66,-.52,-.29,-.06,.17,.4,.63,.86,1.09,1.32,1.48)
    cuts = (.10,.10,.093,.125,.115,.15,.10,.128,.082,.10,.08)
    verts = []
    for x in (-.025,.025):
        for y,z in zip(y_top,cuts):
            verts.append((x,y,z))
        for y in y_top:
            verts.append((x,y,-.045))
    n=len(y_top)
    faces=[]
    for i in range(n-1):
        faces += [(i,i+1,2*n+i+1,2*n+i), (n+i,3*n+i,3*n+i+1,n+i+1)]
        faces += [(i,n+i,n+i+1,i+1),(2*n+i,2*n+i+1,3*n+i+1,3*n+i)]
    faces += [(0,2*n,n*3,n),(n-1,2*n-1,4*n-1,3*n-1)]
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    blade=bpy.data.objects.new("Five-cut nickel key blade",mesh)
    bpy.context.collection.objects.link(blade)
    blade.data.materials.append(nickel)
    blade.parent=carrier
    shaft=box("Key shoulder", (0,-.78,0),(.13,.16,.15),nickel,.02)
    shaft.parent=carrier
    ring=torus("Key bow",(0,-1.05,0),.22,.055,bow_mat,(math.pi/2,0,0))
    ring.parent=carrier
    ring.scale.x=.78
    join=box("Key neck",(0,-.87,0),(.11,.3,.09),nickel,.025)
    join.parent=carrier
    # The hand is attached to the bow and animated with the key. It is mostly
    # shown in three-quarter / over-shoulder views rather than a face-on macro.
    palm=bpy.data.objects.new("Grip anchor",None)
    bpy.context.collection.objects.link(palm)
    palm.parent=carrier
    palm.location=(.085,-1.20,-.12)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=(0,0,0))
    hand=bpy.context.object
    hand.name="Human hand around keyring"
    hand.scale=(.14,.19,.095)
    hand.data.materials.append(glove)
    hand.parent=palm
    for i in range(4):
        finger=cylinder(f"Finger {i+1}",(-.065+i*.046,.09,.01),.024,.2,glove,(math.pi/2,0,0),24)
        finger.parent=palm
    wrist=cylinder("Sleeve to hand",(.04,-.24,-.025),.125,.25,coat,(math.pi/2,0,0),32)
    wrist.parent=palm
    return carrier,cuts,y_top


def tube_half(name, y0, y1, zc, inner, outer, ink, hinge):
    # The open +X half of the housing is cut away for an x-side camera view.
    segments=40
    vertices=[]
    for y in (y0,y1):
        for radius in (outer,inner):
            for j in range(segments+1):
                theta=math.pi/2+math.pi*j/segments
                vertices.append((LOCK_X+radius*math.cos(theta),y,zc+radius*math.sin(theta)))
    span=segments+1
    faces=[]
    for j in range(segments):
        faces.extend([(j,j+1,2*span+j+1,2*span+j),
                      (span+j+1,span+j,3*span+j,3*span+j+1),
                      (j,span+j,span+j+1,j+1),
                      (2*span+j+1,3*span+j+1,3*span+j,2*span+j)])
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(ink)
    put_on_hinge(obj,hinge)
    return obj


def helical_spring(name, ink, hinge):
    curve=bpy.data.curves.new(name,"CURVE")
    curve.dimensions="3D"
    curve.bevel_depth=.008
    curve.bevel_resolution=3
    spline=curve.splines.new("POLY")
    spline.points.add(119)
    for j,p in enumerate(spline.points):
        t=j/119
        theta=math.tau*7*t
        p.co=(.042*math.cos(theta),.042*math.sin(theta),t,1)
    obj=bpy.data.objects.new(name,curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(ink)
    put_on_hinge(obj,hinge)
    return obj


def mechanism(hinge, keyroot, cuts, profile_y, steel, brass, nickel, spring_mat, signal, dark):
    tube_half("One lock housing exposed by door cutaway",.1,1.42,LOCK_Z,.23,.32,steel,hinge)
    plug=tube_half("Single rotating plug cutaway",.12,1.4,LOCK_Z,.15,.225,brass,hinge)
    plug_pivot=put_on_hinge(empt("Plug rotates after pin seams align",(LOCK_X,0,LOCK_Z)),hinge)
    put_on_hinge(plug,plug_pivot)
    key_turn=put_on_hinge(empt("Key turn follows same plug",(LOCK_X,0,LOCK_Z)),hinge)
    put_on_hinge(keyroot,key_turn)
    seam=put_on_hinge(box("Shear line thin cyan guide",(LOCK_X+.18,.74,SHEAR_Z),(.01,1.25,.008),signal,.002),hinge)
    pin_parts=[]
    for i,y in enumerate(PIN_Y):
        lower=put_on_hinge(cylinder(f"Key pin {i+1}",(LOCK_X,y,SHEAR_Z-PIN_HEIGHT[i]/2-.067),.055,PIN_HEIGHT[i],brass,vertices=32),hinge)
        put_on_hinge(lower,plug_pivot)
        driver=put_on_hinge(cylinder(f"Driver pin {i+1}",(LOCK_X,y,SHEAR_Z+.09),.055,.18,nickel,vertices=32),hinge)
        spring=helical_spring(f"Spring {i+1}, compresses with pin",spring_mat,hinge)
        put_on_hinge(torus(f"Upper pin chamber collar {i+1}",(LOCK_X,y,SHEAR_Z+.29),.081,.018,steel),hinge)
        put_on_hinge(torus(f"Lower pin chamber collar {i+1}",(LOCK_X,y,SHEAR_Z+.012),.081,.018,steel),hinge)
        put_on_hinge(cylinder(f"Chamber cap {i+1}",(LOCK_X,y,SHEAR_Z+.37),.09,.045,steel,vertices=32),hinge)
        pin_parts.append((lower,driver,spring))
    # The tailpiece and bolt share the plug's causal turn parameter. The bolt
    # motion is computed from plug angle, rather than a separate unrelated cue.
    tail=put_on_hinge(box("Cylinder tailpiece",(LOCK_X,1.56,LOCK_Z),(.075,.38,.075),nickel,.02),hinge)
    cam=put_on_hinge(cylinder("Cam behind lock",(LOCK_X,1.77,LOCK_Z),.17,.06,brass,(math.pi/2,0,0),48),hinge)
    bolt=put_on_hinge(box("Actual deadbolt retracts into door",(1.29,1.65,LOCK_Z),(.55,.15,.16),steel,.025),hinge)
    bolt_front=put_on_hinge(box("Deadbolt tip",(1.57,1.65,LOCK_Z),(.05,.16,.15),nickel,.01),hinge)
    for part in (bolt,bolt_front):
        for t,hidden in ((0,False),(9.7,False),(10.1,True),
                         (26.35,True),(26.45,False),(28.8,False),(29.15,True)):
            part.hide_render=hidden
            part.keyframe_insert(data_path="hide_render",frame=f(t))
    # The visible key begins by the actor's pocket, approaches the one lock,
    # and completes insertion along the cylinder axis.
    placements=((0,(-.39,-2.0075,1.03)),(1.5,(-.19,-1.66,1.09)),
                (2.2,(.31,-1.15,1.00)),(3.3,(LOCK_X,-.88,1.29)),(6.2,(LOCK_X,-.48,1.29)),
                (9.0,(LOCK_X,-.23,LOCK_Z)),(10.0,(LOCK_X,-.20,LOCK_Z)),
                (10.1,(LOCK_X,-1.50,LOCK_Z)),
                (13.2,(LOCK_X,-1.10,LOCK_Z)),
                (22.5,(LOCK_X,-.20,LOCK_Z)),(28.8,(LOCK_X,-.20,LOCK_Z)),
                (31.5,(-.22,-1.20,1.24)),(35.0,(-.48,-1.51,1.03)))
    for t,loc in placements:
        animate(keyroot,f(t),loc=loc)
    for t,s in ((0,.07),(10.0,.07),(10.1,1),(28.6,1),(29.2,.07)):
        animate(keyroot,f(t),scale=(s,s,s))
    for curve in keyroot.animation_data.action.fcurves:
        for point in curve.keyframe_points:
            if abs(point.co.x-f(10.0))<.01:
                point.interpolation="CONSTANT"
    grip=bpy.data.objects.get("Grip anchor")
    if grip:
        # The rigged character supplies the real hand. These older blockout
        # grip meshes are retained only for editable scene provenance.
        for child in grip.children:
            child.hide_render=True
    # Key insertion, lower pins, drivers and spring compression all use this
    # exact insertion trajectory. Nothing is animated by an independent clock.
    def key_y_at(t):
        for (ta,pa),(tb,pb) in zip(placements,placements[1:]):
            if ta <= t <= tb:
                u=(t-ta)/(tb-ta)
                u=u*u*(3-2*u)
                return pa[1]*(1-u)+pb[1]*u
        return placements[-1][1][1]

    def profile_at(local_y):
        if local_y <= profile_y[0] or local_y >= profile_y[-1]:
            return None
        for k in range(len(profile_y)-1):
            if profile_y[k] <= local_y <= profile_y[k+1]:
                u=(local_y-profile_y[k])/(profile_y[k+1]-profile_y[k])
                return cuts[k]*(1-u)+cuts[k+1]*u
        return None

    final_key_y=next(loc[1] for time,loc in placements if time==22.5)
    final_heights=[profile_at(y-final_key_y) for y in PIN_Y]
    for fr in range(1,END+1,2):
        t=(fr-1)/FPS
        ky=key_y_at(t)
        for i,y in enumerate(PIN_Y):
            cut=profile_at(y-ky)
            # The key profile physically pushes the lower pin. The final cut
            # heights align all five pin-pair seams at the shear line.
            lift=0 if cut is None else max(0,.067+cut)
            lower,driver,spring=pin_parts[i]
            target_lift=.067+final_heights[i]
            animate(lower,fr,loc=(LOCK_X,y,SHEAR_Z-PIN_HEIGHT[i]/2-target_lift+lift))
            animate(driver,fr,loc=(LOCK_X,y,SHEAR_Z+.09-target_lift+lift))
            driver_top=SHEAR_Z+.18-target_lift+lift
            cap_bottom=SHEAR_Z+.3475
            animate(spring,fr,loc=(LOCK_X,y,driver_top),scale=(1,1,max(.07,cap_bottom-driver_top)))
        turn=0 if t<23 else min(1,(t-23)/4.2)
        turn=turn*turn*(3-2*turn)
        angle=turn*math.pi/2
        animate(cam,fr,rot=(math.pi/2,0,angle))
        animate(tail,fr,rot=(0,angle,0))
        animate(bolt,fr,loc=(1.29-.45*turn,1.65,LOCK_Z))
        animate(bolt_front,fr,loc=(1.57-.45*turn,1.65,LOCK_Z))
    for t,angle in ((0,0),(23,0),(27.2,math.pi/2),(END,math.pi/2)):
        animate(plug_pivot,f(t),rot=(0,angle,0))
        animate(key_turn,f(t),rot=(0,angle,0))
    return plug


def cameras(scene):
    bpy.ops.object.camera_add(location=(2.6,-5.9,2.15))
    camera=bpy.context.object
    camera.name="One continuous camera following key into same door"
    camera.data.type="PERSP"
    camera.data.lens=36
    scene.camera=camera
    target=empt("Camera tracking target",(-.15,-.3,1.35))
    con=camera.constraints.new(type="TRACK_TO")
    con.target=target
    con.track_axis="TRACK_NEGATIVE_Z"
    con.up_axis="UP_Y"
    # No snap to a duplicate lock stage: this camera orbits the same geometry.
    shots=[
        (0,(1.8,-4.5,1.95),(-.66,-1.75,1.0),38),
        (1.6,(1.55,-4.1,1.62),(-.35,-1.5,1.05),43),
        (3.3,(1.3,-3.25,1.56),(LOCK_X,-.65,LOCK_Z),49),
        (5.7,(1.12,-1.62,1.51),(.82,-.48,LOCK_Z),50),
        (8.7,(.92,-1.68,1.51),(LOCK_X,-.27,1.39),50),
        (10.0,(.89,-1.57,1.49),(LOCK_X,-.25,1.38),52),
        (10.1,(3.7,-1.3,2.22),(LOCK_X,.57,1.58),60),
        (13.8,(3.7,-1.0,2.15),(LOCK_X,.72,1.58),65),
        (21,(3.6,-.82,2.07),(LOCK_X,.78,1.62),67),
        (25.3,(3.6,-.75,1.95),(LOCK_X,1.12,1.48),65),
        (27.15,(2.25,-2.3,1.93),(1.12,.45,1.4),57),
        (29,(1.76,-2.1,1.7),(LOCK_X,-.3,1.35),49),
        (29.15,(1.5,-6.8,1.9),(0,.2,1.4),31),
        (31.2,(1.55,-6.8,1.9),(0,.2,1.38),31),
        (36,(1.65,-7.2,1.9),(0,.2,1.38),33),
    ]
    for time,pos,look,lens in shots:
        animate(camera,f(time),loc=pos)
        animate(target,f(time),loc=look)
        camera.data.lens=lens
        camera.data.keyframe_insert(data_path="lens",frame=f(time))
    # Explicit jump cuts prevent the virtual camera from flying through the
    # closed door on the way to the inside diagram and back to the hallway.
    for datablock in (camera,target,camera.data):
        for curve in datablock.animation_data.action.fcurves:
            for point in curve.keyframe_points:
                if any(abs(point.co.x-f(time))<.01 for time in (10.0,29.0)):
                    point.interpolation="CONSTANT"
    return camera


def build():
    scene=reset()
    wood=mat("Painted deep walnut door",(.083,.048,.035),0,.48)
    frame_mat=mat("Door frame dark stained wood",(.11,.075,.055),0,.47)
    floor_mat=mat("Concrete hallway floor",(.063,.071,.079),.15,.52)
    wall=mat("Soft blue graphite corridor",(.105,.12,.143),0,.75)
    steel=mat("Dark machined steel lock housing",(.13,.19,.24),.75,.31)
    nickel=mat("Bright brushed nickel key and pin drivers",(.64,.69,.72),.82,.25)
    brass=mat("Warm brass working cylinder",(.48,.29,.11),.85,.25)
    dark=mat("Almost black keyway",(.006,.008,.011),0,.85)
    skin=mat("Person skin",(.49,.32,.24),0,.65)
    coat=mat("Person navy jacket",(.025,.051,.076),.05,.63)
    signal=material("Shear alignment cool signal",(.03,.69,.87),.05,.27,.42)
    hinge,door,plug_face,keyhole=door_set(wood,frame_mat,floor_mat,wall,nickel,brass,dark)
    actor(skin,coat)
    keyroot,cuts,profile_y=key_mesh(skin,nickel,brass,coat)
    mechanism(hinge,keyroot,cuts,profile_y,steel,brass,nickel,nickel,signal,dark)
    def descendants(obj):
        for child in obj.children:
            yield child
            yield from descendants(child)
    for part in descendants(keyroot):
        if part.type in {"MESH","CURVE"}:
            for t,hidden in ((0,False),(28.8,False),(29.0,True)):
                part.hide_render=hidden
                part.keyframe_insert(data_path="hide_render",frame=f(t))
    internal_prefixes=("One lock housing","Single rotating plug","Shear line",
                       "Key pin","Driver pin","Spring ","Upper pin chamber",
                       "Lower pin chamber","Chamber cap","Cylinder tailpiece",
                       "Cam behind lock")
    for part in bpy.data.objects:
        if part.name.startswith(internal_prefixes) and part.type in {"MESH","CURVE"}:
            for t,hide in ((0,True),(9.7,True),(10.1,False),(28.6,False),(29,True)):
                part.hide_render=hide
                part.keyframe_insert(data_path="hide_render",frame=f(t))
    area("Large softbox above corridor",(-2.5,-4.5,4.8),1250,(.62,.76,1),4.0,(0,0,1.5))
    area("Warm inner house backlight",(.3,2.9,2.8),900,(1,.65,.35),2.4,(0,0,1.5))
    area("Macro rim light",(1.6,.8,2.25),850,(.24,.75,1),1.65,(LOCK_X,.75,1.4))
    cameras(scene)
    # Hide only the door slab during the inside view. It is the exact same door;
    # the remaining frame, escutcheon and mechanism never move to a new set.
    shell_prefixes=("Single real door slab","Raised door panel","Door stile highlight",
                    "Handle round rosette","Handle spindle","Lever handle",
                    "Escutcheon black gasket","Brushed metal escutcheon",
                    "Brass plug face","Black inner keyway","Escutcheon screw")
    for part in bpy.data.objects:
        if part.name.startswith(shell_prefixes):
            for t,hide in ((0,False),(9.7,False),(10.1,True),(28.6,True),(29,False)):
                part.hide_render=hide
                part.keyframe_insert(data_path="hide_render",frame=f(t))
    for part in bpy.data.objects:
        if part.name.startswith(("Wall left of door","Wall right of door",
                                 "Wall over door","Door frame vertical",
                                 "Door frame header","Wall baseboard",
                                 "Hall concrete floor","Interior floor",
                                 "Warm interior back wall",
                                 "Warm hallway lamp fixture")):
            for t,hide in ((0,False),(9.7,False),(10.1,True),(28.6,True),(29,False)):
                part.hide_render=hide
                part.keyframe_insert(data_path="hide_render",frame=f(t))
    return scene


def main():
    args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("preview","render","build"))
    parser.add_argument("frames",nargs="*",type=int)
    parser.add_argument("--start",type=int,default=1)
    parser.add_argument("--end",type=int,default=END)
    parser.add_argument("--force",action="store_true")
    opts=parser.parse_args(args)
    OUT.mkdir(parents=True,exist_ok=True)
    scene=build()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"lock-cinematic-v4.blend"))
    if opts.mode=="build":
        return
    frames=opts.frames or ([1,55,105,170,260,365,500,610,710,820] if opts.mode=="preview" else range(opts.start,opts.end+1))
    frame_dir=OUT/("previews" if opts.mode=="preview" else "frames")
    frame_dir.mkdir(parents=True,exist_ok=True)
    for frame in frames:
        result=frame_dir/f"frame_{frame:04d}.png"
        if not opts.force and result.exists() and result.stat().st_size>1000:
            continue
        scene.frame_set(frame)
        scene.render.filepath=str(result)
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {frame}/{END}: {result}",flush=True)


if __name__=="__main__":
    main()

"""Tiny World garage template: a die-cast style car on a display stand inside a tiny garage diorama + locked camera path.
Run: Blender -b -P blender/garage.py -- <out_dir> [car_mesh.obj]
With a mesh (photo -> 3D, tools/object_clay.py) the clay car is the user's own car shape, turned so the view it was
photographed from faces the last camera position: the tiny car and the real photo line up at the cut.
Writes <out_dir>/garage.blend, clay frames (PNG) and first_frame.png.
576x1024 (9:16), 24 fps, 177 frames (8k+1). The open front of the garage faces -Y; the car faces front-left, ending on a
three-quarter front view (how most people photograph their car)."""
import bpy, math, os, sys

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(ARGS[0] if ARGS else "templates/garage")
MESH = ARGS[1] if len(ARGS) > 1 else None
FRAMES, FPS, W, H = 177, 24, 576, 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def box(name, loc, size):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object; o.name = name; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    return o

def cyl(name, loc, r, d, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d, location=loc)
    o = bpy.context.object; o.name = name; return o

# Desk world + the garage box. Garage floor top is z=0, floor spans x -1.4..1.4, y -0.6..1.6.
box("table", (0, 0, -0.45), (40, 40, 0.1))
box("back_wall_far", (0, 14, 6), (40, 0.2, 14))
box("base", (0, 0.5, -0.2), (3.2, 2.6, 0.4))
box("floor", (0, 0.5, -0.01), (2.8, 2.2, 0.02))
box("wall_back", (0, 1.62, 0.65), (2.84, 0.04, 1.3))
box("wall_L", (-1.42, 0.5, 0.65), (0.04, 2.24, 1.3))
box("wall_R", (1.42, 0.5, 0.65), (0.04, 2.24, 1.3))
box("roll_door", (0, -0.55, 1.22), (2.7, 0.12, 0.16))          # raised roll-up door at the open front
for x in (-0.7, 0.7): box(f"ceiling_light_{x}", (x, 0.6, 1.2), (0.5, 0.06, 0.03))
# Workshop props: workbench + tool wall at the back, tyre stack, toolbox, oil can, floor stripe
box("bench", (-0.6, 1.4, 0.32), (1.1, 0.3, 0.04))
for x in (-1.1, -0.1): box(f"bench_leg_{x}", (x, 1.4, 0.15), (0.04, 0.26, 0.3))
box("tool_board", (-0.6, 1.59, 0.75), (1.0, 0.02, 0.45))
for i, z in enumerate((0.07, 0.19, 0.31)): cyl(f"tyre_{i}", (1.12, 1.25, z), 0.16, 0.11, 32)
box("toolbox", (1.1, 0.4, 0.2), (0.25, 0.4, 0.4))
cyl("oil_can", (-1.2, 0.2, 0.06), 0.05, 0.12, 16)
box("display_stand", (0, 0.35, 0.03), (1.6, 1.0, 0.06))
if MESH:
    # TripoSR meshes are Z-up; the photo was taken from the mesh's +X side.
    bpy.ops.wm.obj_import(filepath=MESH, up_axis="Z", forward_axis="Y")
    car = bpy.context.selected_objects[0]; car.name = "car"
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    car.scale = (1.4 / max(car.dimensions.x, car.dimensions.y),) * 3       # same length as the proxy car
    bpy.ops.object.transform_apply(scale=True)
    car.location = (0, 0.35, 0.06 + car.dimensions.z / 2)
    # point the photographed side (+X) at the final camera position (0.14, -2.25)
    car.rotation_euler = (0, 0, math.atan2(-2.25 - 0.35, 0.14 - 0.0))
else:
    # Car proxy on the stand: body, cabin, four wheels; nose points front-left
    parts = [box("car_body", (0, 0, 0.17), (0.62, 1.4, 0.22)), box("car_cabin", (0, 0.08, 0.37), (0.56, 0.72, 0.2))]
    for i, (x, y) in enumerate([(-0.31, -0.45), (0.31, -0.45), (-0.31, 0.45), (0.31, 0.45)]):
        w = cyl(f"wheel_{i}", (x, y, 0.1), 0.1, 0.1, 32); w.rotation_euler = (0, math.radians(90), 0); parts.append(w)
    bpy.ops.object.empty_add(location=(0, 0.35, 0.06)); car = bpy.context.object; car.name = "car"
    for o in parts: o.parent = car
    car.rotation_euler = (0, 0, math.radians(-35))

# Camera: high establishing over the garage -> crane down -> low three-quarter front of the car = cut point to the real photo
bpy.ops.object.empty_add(location=(0, 0.5, 0.3)); tgt = bpy.context.object; tgt.name = "cam_target"
bpy.ops.object.camera_add(); cam = bpy.context.object; cam.name = "cam"; sc.camera = cam
cam.data.lens = 35; cam.data.sensor_width = 36; cam.data.clip_start = 0.01
c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
KEYS = [  # frame, camera xyz, target xyz
    (1,   (0.0, -4.8, 4.4),  (0.0, 0.5, 0.2)),    # high establishing, the whole garage box on its base
    (60,  (-2.0, -3.6, 2.0), (0.0, 0.5, 0.3)),    # crane down + arc left
    (125, (-0.6, -2.6, 0.75), (0.0, 0.4, 0.28)),  # low, outside the door, car in front
    (177, (0.14, -2.25, 0.68), (0.0, 0.35, 0.24)),  # 35 degrees off the nose = three-quarter front, whole car in frame = cut point
]
for f, cl, tl in KEYS:
    cam.location = cl; cam.keyframe_insert("location", frame=f)
    tgt.location = tl; tgt.keyframe_insert("location", frame=f)

sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "SINGLE"; sh.single_color = (0.62, 0.62, 0.6)
sh.show_cavity = True; sh.cavity_type = "BOTH"; sh.show_shadows = True
sc.display.shadow_focus = 0.6
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.image_settings.file_format = "PNG"
os.makedirs(OUT + "/clay_frames", exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT + "/garage.blend")
sc.frame_set(1); sc.render.filepath = OUT + "/first_frame.png"; bpy.ops.render.render(write_still=True)
sc.render.filepath = OUT + "/clay_frames/f_"; bpy.ops.render.render(animation=True)

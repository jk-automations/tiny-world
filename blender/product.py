"""Tiny World product template: the product as a giant monument in a miniature town square.
Run: Blender -b -P blender/product.py -- <out_dir>
Writes <out_dir>/product.blend, clay frames (PNG) and first_frame.png.
576x1024 (9:16, divisible by 64), 24 fps, 177 frames (8k+1)."""
import bpy, math, os, sys

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(ARGS[0] if ARGS else "templates/product-pedestal")
SHAPE = ARGS[1] if len(ARGS) > 1 else "tall"
MESH = ARGS[2] if len(ARGS) > 2 else None   # SHAPE "mesh": the user's own object (photo -> 3D, TripoSR), see tools/object_clay.py   # tall (bottle/box, default) | jar (short and wide: jars, tins, candles) | car (a car on a turntable)
assert SHAPE in ("tall", "jar", "car", "mesh"), SHAPE
FRAMES, FPS, W, H = 177, 24, 576, 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def box(name, loc, size):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object; o.name = name; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    return o

def cyl(name, loc, r, d, verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=d, location=loc)
    o = bpy.context.object; o.name = name; return o

def cone(name, loc, r, d):
    bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=r, depth=d, location=loc)
    o = bpy.context.object; o.name = name; return o

def person(name, x, y):
    """Painted-figure proxy ~0.18 tall: two legs, torso, arms, head, so the model keeps a human shape."""
    for i, dx in enumerate((-0.012, 0.012)):
        cyl(f"{name}_leg{i}", (x + dx, y, 0.04), 0.009, 0.08, 10)
    cyl(name + "_torso", (x, y, 0.11), 0.022, 0.07, 14)
    for i, dx in enumerate((-0.03, 0.03)):
        cyl(f"{name}_arm{i}", (x + dx, y, 0.105), 0.007, 0.06, 8)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.02, location=(x, y, 0.165))
    bpy.context.object.name = name + "_head"

# Diorama world: plinth top is z=0. Product proxy stands on a stepped pedestal at the centre.
cyl("plinth", (0, 0, -0.2), 3.0, 0.4, 96)
box("table", (0, 0, -0.45), (40, 40, 0.1))
box("back_wall", (0, 14, 4), (40, 0.2, 9))
cyl("plaza", (0, 0, 0.01), 2.6, 0.02, 96)
cyl("step_1", (0, 0.3, 0.06), 0.75, 0.1, 64)
cyl("step_2", (0, 0.3, 0.16), 0.6, 0.1, 64)
TALL = SHAPE == "tall"
if SHAPE == "mesh":
    # TripoSR meshes are Z-up and were photographed from their +X side: turn that side to the final camera (straight on, -Y).
    bpy.ops.wm.obj_import(filepath=MESH, up_axis="Z", forward_axis="Y")
    obj = bpy.context.selected_objects[0]; obj.name = "product"
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    TALL = obj.dimensions.z >= max(obj.dimensions.x, obj.dimensions.y)
    obj.scale = ((1.3 / obj.dimensions.z) if TALL else (0.9 / max(obj.dimensions.x, obj.dimensions.y)),) * 3
    bpy.ops.object.transform_apply(scale=True)
    obj.location = (0, 0.3, 0.21 + obj.dimensions.z / 2); obj.rotation_euler = (0, 0, math.radians(-90))
elif SHAPE == "car":
    # low car proxy angled 30 degrees on the top step (z 0.21): body, cabin, four wheels, so the model keeps a car silhouette
    parts = [box("car_body", (0, 0, 0.17), (0.62, 1.4, 0.22)), box("car_cabin", (0, 0.08, 0.37), (0.56, 0.72, 0.2))]
    for i, (x, y) in enumerate([(-0.31, -0.45), (0.31, -0.45), (-0.31, 0.45), (0.31, 0.45)]):
        w = cyl(f"wheel_{i}", (x, y, 0.1), 0.1, 0.1, 32); w.rotation_euler = (0, math.radians(90), 0); parts.append(w)
    bpy.ops.object.empty_add(location=(0, 0.3, 0.21)); car = bpy.context.object; car.name = "car"
    for o in parts: o.parent = car
    car.rotation_euler = (0, 0, math.radians(-30))
elif SHAPE == "jar":
    cyl("product", (0, 0.3, 0.485), 0.42, 0.55, 64)           # short wide jar proxy on the top step (z 0.21)
    cyl("product_cap", (0, 0.3, 0.82), 0.44, 0.12, 64)
else:
    box("product", (0, 0.3, 0.86), (0.6, 0.4, 1.3))           # generic product proxy, replaced by the user's product
    box("product_cap", (0, 0.3, 1.56), (0.36, 0.28, 0.1))
# Square edges: little buildings, trees, lamps, benches, figures looking at the product
for i, (x, y, h) in enumerate([(-2.0, 1.4, 0.7), (-1.2, 2.0, 0.9), (1.2, 2.0, 0.8), (2.0, 1.4, 0.6)]):
    box(f"house_{i}", (x, y, h / 2), (0.6, 0.5, h))
for i, (x, y) in enumerate([(-1.6, 0.2), (1.6, 0.2), (-1.5, -1.0), (1.0, -1.3)]):
    cyl(f"tree_{i}_trunk", (x, y, 0.08), 0.02, 0.16, 12); cone(f"tree_{i}", (x, y, 0.32), 0.16, 0.36)
for i, x in enumerate((-0.9, 0.9)):
    cyl(f"lamp_{i}", (x, -0.4, 0.3), 0.015, 0.6, 12)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, location=(x, -0.4, 0.62))
box("bench_L", (-0.6, -0.75, 0.07), (0.3, 0.08, 0.04)); box("bench_R", (0.6, -0.75, 0.07), (0.3, 0.08, 0.04))
for i, (x, y) in enumerate([(-0.35, -0.55), (0.3, -0.6), (0.05, -0.9), (-0.8, -0.2), (0.85, -0.1), (-0.5, -1.1)]):
    person(f"p{i}", x, y)

# Camera: Track-To an animated target. Bezier keys, auto-clamped ease.
bpy.ops.object.empty_add(location=(0, 0, 0.6)); tgt = bpy.context.object; tgt.name = "cam_target"
bpy.ops.object.camera_add(); cam = bpy.context.object; cam.name = "cam"; sc.camera = cam
cam.data.lens = 35; cam.data.sensor_width = 36; cam.data.clip_start = 0.01
c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
KEYS = [  # frame, camera xyz, target xyz
    (1,   (0.0, -5.6, 4.4),  (0.0, 0.2, 0.4)),    # high establishing, plinth fills the frame width
    (60,  (-2.4, -4.0, 2.0), (0.0, 0.3, 0.6)),    # orbit left + descend
    (125, (-0.5, -2.0, 0.25), (0.0, 0.3, 0.9)),   # low hero angle, looking up at the product
    (160, (0.0, -1.7, 0.6),  (0.0, 0.3, 0.85)),   # push in
    (177, (0.0, -1.1, 0.86), (0.0, 0.3, 0.86)),   # product fills most of the frame, edges visible = cut point to the real photo
]
if not TALL:   # same move, aimed lower at a shorter product
    KEYS = [(1, (0.0, -5.6, 4.4), (0.0, 0.2, 0.3)), (60, (-2.4, -4.0, 2.0), (0.0, 0.3, 0.45)),
            (125, (-0.5, -2.0, 0.2), (0.0, 0.3, 0.55)), (160, (0.0, -2.0, 0.5), (0.0, 0.3, 0.5)), (177, (0.0, -1.65, 0.55), (0.0, 0.3, 0.5))]
    bpy.data.objects["back_wall"].scale.z = 12
    if SHAPE == "car":   # the car is longer: end further back so the whole car stays in frame
        KEYS[-2] = (160, (0.0, -2.6, 0.6), (0.0, 0.3, 0.42)); KEYS[-1] = (177, (0.0, -2.25, 0.62), (0.0, 0.3, 0.42))   # the low camera looks up more; keep wall behind the whole frame
for f, cl, tl in KEYS:
    cam.location = cl; cam.keyframe_insert("location", frame=f)
    tgt.location = tl; tgt.keyframe_insert("location", frame=f)
for o in (cam, tgt):
    for fc in o.animation_data.action.fcurves if hasattr(o.animation_data.action, "fcurves") else []:
        for k in fc.keyframe_points: k.interpolation = "BEZIER"; k.handle_left_type = k.handle_right_type = "AUTO_CLAMPED"

# Clay look: Workbench, single neutral grey, cavity + shadows (fast, headless-safe).
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "SINGLE"; sh.single_color = (0.62, 0.62, 0.6)
sh.show_cavity = True; sh.cavity_type = "BOTH"; sh.show_shadows = True
sc.display.shadow_focus = 0.6
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
sc.render.fps = FPS; sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.image_settings.file_format = "PNG"
os.makedirs(OUT + "/clay_frames", exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT + "/product.blend")
sc.frame_set(1); sc.render.filepath = OUT + "/first_frame.png"; bpy.ops.render.render(write_still=True)
sc.render.filepath = OUT + "/clay_frames/f_"; bpy.ops.render.render(animation=True)

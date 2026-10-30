"""Camera moves (env TINYWORLD_MOVE): crane (default, high establishing -> door) | street (low glide along the street -> door).
Tiny World storefront template: diorama blockout + locked camera path.
Run: Blender -b -P blender/storefront.py -- <out_dir> [shape]
Shapes: flat2 (two storeys, flat roof; default), pitched2 (two storeys, gable roof + chimney), wide1 (one storey, wide front),
house (pitched2 without shop parts: small porch roof over the door, house-size windows, no sign).
Writes <out_dir>/storefront.blend, clay frames (PNG) and first_frame.png.
576x1024 (9:16, divisible by 64), 24 fps, 177 frames (8k+1)."""
import bpy, math, os, sys

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(ARGS[0] if ARGS else "templates/storefront")
SHAPE = ARGS[1] if len(ARGS) > 1 else "flat2"
assert SHAPE in ("flat2", "pitched2", "wide1", "house"), SHAPE
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

# Diorama world: plinth top is z=0. Shop front faces -Y at y=0.4.
cyl("plinth", (0, 0.4, -0.2), 3.0, 0.4, 96)
box("table", (0, 0, -0.45), (40, 40, 0.1))
box("back_wall", (0, 14, 4), (40, 0.2, 9))
box("street", (0, -0.85, 0.01), (5.2, 1.1, 0.02))
box("sidewalk", (0, 0.05, 0.03), (5.0, 0.7, 0.06))
# Building with recessed door and windows (recess = darker cavity in clay). The door, sign and awning sit at the same
# height in every shape, so the camera path is shared.
BW, BH = (3.4, 1.1) if SHAPE == "wide1" else (2.4, 1.8)
box("building", (0, 1.2, BH / 2), (BW, 1.6, BH))
box("door_recess", (0, 0.7, 0.4), (0.42, 0.7, 0.8))        # deep doorway, reads dark
wx, ww = (1.0, 1.0) if SHAPE == "wide1" else (0.7, 0.45) if SHAPE == "house" else (0.75, 0.7)
box("window_L", (-wx, 0.42, 0.55), (ww, 0.08, 0.6))
box("window_R", (wx, 0.42, 0.55), (ww, 0.08, 0.6))
holes = ["door_recess", "window_L", "window_R"]
if SHAPE != "wide1":
    box("window_up_L", (-0.6, 0.42, 1.35), (0.45, 0.06, 0.4))
    box("window_up_R", (0.6, 0.42, 1.35), (0.45, 0.06, 0.4))
    holes += ["window_up_L", "window_up_R"]
bld = bpy.data.objects["building"]
for n in holes:
    m = bld.modifiers.new(n, "BOOLEAN"); m.operation = "DIFFERENCE"; m.object = bpy.data.objects[n]
    bpy.data.objects[n].hide_render = True; bpy.data.objects[n].hide_viewport = True
if SHAPE == "house":
    box("porch_roof", (0, 0.25, 0.9), (0.8, 0.4, 0.04)).rotation_euler = (math.radians(-15), 0, 0)
else:
    box("sign", (0, 0.33, 0.95), (1.6 if SHAPE == "wide1" else 1.2, 0.06, 0.22))
    box("awning", (0, 0.22, 0.88), (BW - 0.1, 0.4, 0.04)).rotation_euler = (math.radians(-12), 0, 0)
if SHAPE in ("pitched2", "house"):
    # gable roof: a triangular prism along the depth, ridge 0.7 above the eaves, plus a chimney
    me = bpy.data.meshes.new("roof"); hw, y0, y1, z0 = BW / 2 + 0.08, 0.35, 2.05, BH
    me.from_pydata([(-hw, y0, z0), (hw, y0, z0), (0, y0, z0 + 0.7), (-hw, y1, z0), (hw, y1, z0), (0, y1, z0 + 0.7)], [],
                   [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)])
    roof = bpy.data.objects.new("roof", me); sc.collection.objects.link(roof)
    box("chimney", (0.7, 1.5, BH + 0.55), (0.2, 0.2, 0.6))
else:
    box("roof_trim", (0, 1.2, BH + 0.03), (BW + 0.1, 1.7, 0.06))
nx, nw = (2.2, 0.9) if SHAPE == "wide1" else (2.05, 1.5)
box("neighbor_L", (-nx, 1.4, 0.6), (nw, 1.4, 1.2))
box("neighbor_R", (nx, 1.4, 0.75), (nw, 1.4, 1.5))
# Street props
box("car", (-1.1, -0.75, 0.1), (0.5, 0.22, 0.16))
box("car_cab", (-1.12, -0.75, 0.21), (0.28, 0.2, 0.1))
cyl("lamp_post", (1.35, -0.2, 0.3), 0.015, 0.6, 12)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, location=(1.35, -0.2, 0.62))
cyl("tree_L_trunk", (-1.9, -0.15, 0.08), 0.02, 0.16, 12); cone("tree_L", (-1.9, -0.15, 0.32), 0.17, 0.38)
cyl("tree_R_trunk", (1.95, -0.15, 0.08), 0.02, 0.16, 12); cone("tree_R", (1.95, -0.15, 0.32), 0.17, 0.38)
box("bench", (-0.7, -0.1, 0.07), (0.3, 0.08, 0.04))
box("planter_L", (-0.38, 0.3, 0.1), (0.12, 0.12, 0.12)); box("planter_R", (0.38, 0.3, 0.1), (0.12, 0.12, 0.12))
person("p1", 0.55, 0.05); person("p2", -0.25, -0.05); person("p3", 1.7, 0.1)

# Camera: Track-To an animated target. Bezier keys, auto-clamped ease.
bpy.ops.object.empty_add(location=(0, 0, 0.6)); tgt = bpy.context.object; tgt.name = "cam_target"
bpy.ops.object.camera_add(); cam = bpy.context.object; cam.name = "cam"; sc.camera = cam
cam.data.lens = 35; cam.data.sensor_width = 36; cam.data.clip_start = 0.01
c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
KEYS = [  # frame, camera xyz, target xyz
    (1,   (0.0, -5.6, 4.4),  (0.0, 0.5, 0.25)),   # high establishing, plinth fills the frame width
    (60,  (2.2, -4.4, 2.2),  (0.0, 0.6, 0.45)),    # crane down + arc right
    (130, (0.6, -2.6, 0.45), (0.0, 0.8, 0.4)),    # street level, facing the shop
    (160, (0.0, -0.9, 0.4),  (0.0, 1.0, 0.4)),    # push to the door
    (177, (0.0, -0.12, 0.4), (0.0, 1.2, 0.4)),   # doorway fills the frame = cut point to the real photo
]
MOVE = os.environ.get("TINYWORLD_MOVE", "crane")
if MOVE == "street":
    KEYS = [  # low street-level glide past the neighbours, then turn and push into the door (same end frame as "crane")
        (1,   (-3.4, -3.0, 0.9),  (-0.3, 0.6, 0.45)),
        (60,  (-1.4, -2.4, 0.7),  (0.0, 0.7, 0.45)),
        (110, (0.9, -1.6, 0.5),   (0.0, 0.8, 0.42)),
        (150, (0.1, -0.9, 0.4),   (0.0, 1.0, 0.4)),
        (177, (0.0, -0.12, 0.4),  (0.0, 1.2, 0.4)),
    ]
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
bpy.ops.wm.save_as_mainfile(filepath=OUT + "/storefront.blend")
sc.frame_set(1); sc.render.filepath = OUT + "/first_frame.png"; bpy.ops.render.render(write_still=True)
sc.render.filepath = OUT + "/clay_frames/f_"; bpy.ops.render.render(animation=True)

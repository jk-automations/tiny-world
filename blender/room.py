"""Camera moves (env TINYWORLD_MOVE): crane (default, dollhouse from the front -> desk) | dropin (straight down from above -> desk).
Tiny World room template: a dollhouse-style cutaway room (bedroom / PC setup) on a wooden base + locked camera path.
Run: Blender -b -P blender/room.py -- <out_dir>
Writes <out_dir>/room.blend, clay frames (PNG) and first_frame.png.
576x1024 (9:16), 24 fps, 177 frames (8k+1). The open side of the room faces -Y; the desk is centred on the back wall."""
import bpy, math, os, sys

OUT = os.path.abspath(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else os.path.abspath("templates/room")
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

# Desk world + the room box. Room floor top is z=0, floor spans x -1.2..1.2, y -0.5..1.5.
box("table", (0, 0, -0.45), (40, 40, 0.1))
box("back_wall_far", (0, 14, 4), (40, 0.2, 9))
box("base", (0, 0.5, -0.2), (2.8, 2.4, 0.4))                    # wooden base the room sits on
box("floor", (0, 0.5, -0.01), (2.4, 2.0, 0.02))
box("wall_back", (0, 1.52, 0.7), (2.44, 0.04, 1.4))
box("wall_L", (-1.22, 0.5, 0.7), (0.04, 2.08, 1.4))
box("wall_R", (1.22, 0.5, 0.7), (0.04, 2.08, 1.4))
win = box("win_hole", (-0.75, 1.52, 0.85), (0.55, 0.2, 0.45)); wb = bpy.data.objects["wall_back"]
m = wb.modifiers.new("win", "BOOLEAN"); m.operation = "DIFFERENCE"; m.object = win; win.hide_render = win.hide_viewport = True
# Desk setup centred on the back wall: wide desk, three monitors in a row, tower, keyboard, lamp. No chair: the
# image model and the video model never agreed on where a chair goes (2026-10-27: double chairs, moving monitors),
# and the real photo shows the real chair anyway.
box("desk", (0.1, 1.25, 0.37), (1.3, 0.45, 0.04))
for x in (-0.48, 0.68): box(f"desk_leg_{x}", (x, 1.25, 0.18), (0.04, 0.4, 0.36))
for i, x in enumerate((-0.33, 0.1, 0.53)):
    box(f"monitor_{i}", (x, 1.38, 0.62), (0.4, 0.03, 0.25)); box(f"monitor_stand_{i}", (x, 1.38, 0.43), (0.05, 0.05, 0.08))
box("keyboard", (0.1, 1.15, 0.4), (0.36, 0.1, 0.02))
box("tower", (0.95, 1.25, 0.24), (0.2, 0.42, 0.48))
cyl("lamp_post", (-0.35, 1.38, 0.5), 0.01, 0.22, 8); cyl("lamp_shade", (-0.35, 1.38, 0.63), 0.05, 0.06, 16)
# Rest of the room: bed on the left, shelf on the right wall, rug, plant, poster
box("bed", (-0.85, 0.3, 0.12), (0.6, 1.1, 0.24)); box("pillow", (-0.85, 0.75, 0.27), (0.45, 0.16, 0.07))
box("headboard", (-0.85, 0.87, 0.3), (0.62, 0.04, 0.6))
box("shelf", (1.12, 0.3, 0.75), (0.16, 0.6, 0.03)); box("shelf2", (1.12, 0.3, 1.0), (0.16, 0.6, 0.03))
box("rug", (0.05, 0.4, 0.005), (0.9, 0.7, 0.01))
cyl("plant_pot", (0.95, 0.75, 0.08), 0.07, 0.16); bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(0.95, 0.75, 0.27))
box("poster", (0.6, 1.49, 1.05), (0.32, 0.01, 0.42))

# Camera: high dollhouse view -> descend + arc -> push in over the chair to the desk = cut point to the real photo
bpy.ops.object.empty_add(location=(0, 0.5, 0.5)); tgt = bpy.context.object; tgt.name = "cam_target"
bpy.ops.object.camera_add(); cam = bpy.context.object; cam.name = "cam"; sc.camera = cam
cam.data.lens = 35; cam.data.sensor_width = 36; cam.data.clip_start = 0.01
c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
KEYS = [  # frame, camera xyz, target xyz
    (1,   (0.0, -4.6, 4.2),  (0.0, 0.5, 0.2)),    # high establishing, the whole room box on its base
    (60,  (1.9, -3.4, 2.0),  (0.0, 0.7, 0.4)),    # crane down + arc right
    (130, (0.5, -1.4, 0.85), (0.1, 1.0, 0.5)),    # tiny eye level at the open side
    (160, (0.12, -0.6, 0.9),  (0.1, 1.2, 0.55)),   # push in to the desk
    (177, (0.1, -0.2, 0.82),  (0.1, 1.38, 0.55)), # desk + all three monitors fill the frame = cut point to the real photo
]
MOVE = os.environ.get("TINYWORLD_MOVE", "crane")
if MOVE == "dropin":
    KEYS = [  # straight down into the open dollhouse from above, then settle at the desk (same end frame as "crane")
        (1,   (0.0, 0.05, 4.6),   (0.0, 0.6, 0.0)),
        (60,  (0.0, -0.3, 2.3),   (0.0, 0.8, 0.3)),
        (120, (0.05, -0.55, 1.25), (0.1, 1.1, 0.5)),
        (177, (0.1, -0.2, 0.82),  (0.1, 1.38, 0.55)),
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
bpy.ops.wm.save_as_mainfile(filepath=OUT + "/room.blend")
sc.frame_set(1); sc.render.filepath = OUT + "/first_frame.png"; bpy.ops.render.render(write_still=True)
sc.render.filepath = OUT + "/clay_frames/f_"; bpy.ops.render.render(animation=True)

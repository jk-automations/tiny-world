import bpy, sys, math, os
a = sys.argv[sys.argv.index("--") + 1:]; mesh, out = a[0], a[1]
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
bpy.ops.wm.obj_import(filepath=mesh, up_axis=a[2] if len(a) > 2 else "Y", forward_axis=a[3] if len(a) > 3 else "NEGATIVE_Z")
o = bpy.context.selected_objects[0]
d = max(o.dimensions); o.scale = (2 / d,) * 3; bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS"); o.location = (0, 0, 0)
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam; cam.data.lens = 50
bpy.ops.object.empty_add(); t = bpy.context.object
c = cam.constraints.new("TRACK_TO"); c.target = t; c.track_axis = "TRACK_NEGATIVE_Z"; c.up_axis = "UP_Y"
sc.render.engine = "BLENDER_WORKBENCH"; sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "SINGLE"; sh.show_cavity = True
sc.render.resolution_x = sc.render.resolution_y = 384
for i, ang in enumerate((0, 90, 180, 270)):
    r = math.radians(ang); cam.location = (5 * math.sin(r), -5 * math.cos(r), 2)
    sc.render.filepath = f"{out}_{i}.png"; bpy.ops.render.render(write_still=True)
print("dims", tuple(round(x, 2) for x in o.dimensions))

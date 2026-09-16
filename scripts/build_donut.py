"""Build a pink-frosted donut, plate, drop+squish animation, and exports."""
from __future__ import annotations

import math
import os
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
EXPORT = ROOT / "export"
BLEND = ROOT / "donut.blend"

MAJOR = 0.92
MINOR = 0.38
ROOT_Z = 0.44
PLATE_TOP = 0.07
FPS = 24
END = 96
SEED = 7
N_SPRINKLES = 48


def socket(bsdf, *names):
    for name in names:
        if name in bsdf.inputs:
            return bsdf.inputs[name]
    return None


def set_in(bsdf, names, value):
    sock = socket(bsdf, *names) if isinstance(names, (list, tuple)) else socket(bsdf, names)
    if sock is None:
        return
    sock.default_value = value


def principled(name, color, rough=0.45, spec=0.45, coat=0.0, sss=0.0, trans=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    set_in(bsdf, ("Base Color", "Base Color"), (*color, 1.0))
    set_in(bsdf, ("Roughness",), rough)
    set_in(bsdf, ("Specular IOR Level", "Specular"), spec)
    set_in(bsdf, ("Coat Weight", "Clearcoat"), coat)
    set_in(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.12)
    set_in(bsdf, ("Subsurface Weight", "Subsurface"), sss)
    set_in(bsdf, ("Transmission Weight", "Transmission"), trans)
    mat.diffuse_color = (*color, 1.0)
    return mat


def shade_smooth(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = True


def clear_scene():
    if bpy.app.background:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        return
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights, bpy.data.curves, bpy.data.actions):
        for item in list(coll):
            coll.remove(item)


def new_mesh_obj(op, name, **kwargs):
    bpy.ops.object.select_all(action="DESELECT")
    op(**kwargs)
    obj = bpy.context.active_object
    obj.name = name
    if obj.data:
        obj.data.name = name
    return obj


def add_torus(name, major, minor, z, segments=(64, 32)):
    return new_mesh_obj(
        bpy.ops.mesh.primitive_torus_add,
        name,
        align="WORLD",
        location=(0.0, 0.0, z),
        major_segments=segments[0],
        minor_segments=segments[1],
        mode="MAJOR_MINOR",
        major_radius=major,
        minor_radius=minor,
    )


def frosting_from_torus(src, name):
    mesh = src.data.copy()
    mesh.name = name
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.location = src.location.copy()
    obj.location.z += 0.04
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    dead = [v for v in bm.verts if v.co.z < 0.04]
    bmesh.ops.delete(bm, geom=dead, context="VERTS")
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    for v in bm.verts:
        if v.is_boundary:
            ang = math.atan2(v.co.y, v.co.x)
            drip = max(0.0, math.sin(ang * 5.0 + 0.6)) ** 2.4
            v.co.z -= 0.11 * drip
            v.co.x *= 1.0 + 0.015 * drip
            v.co.y *= 1.0 + 0.015 * drip
    bm.to_mesh(mesh)
    bm.free()
    solid = obj.modifiers.new("Solidify", "SOLIDIFY")
    solid.thickness = 0.055
    solid.offset = 1.0
    sub = obj.modifiers.new("Subsurf", "SUBSURF")
    sub.levels = 2
    sub.render_levels = 2
    return obj


def apply_mods(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.select_set(False)


def key(obj, data_path, frame, value, interp="BEZIER"):
    if data_path == "location":
        obj.location = value
    elif data_path == "scale":
        obj.scale = value
    elif data_path == "rotation_euler":
        obj.rotation_euler = value
    obj.keyframe_insert(data_path=data_path, frame=frame)
    try:
        ad = obj.animation_data
        action = ad.action if ad else None
        curves = getattr(action, "fcurves", None)
        if curves is None and action is not None:
            curves = action.layers[0].strips[0].channelbag.fcurves
        for fc in curves or []:
            if fc.data_path != data_path:
                continue
            for kp in fc.keyframe_points:
                if int(kp.co.x) == int(frame):
                    kp.interpolation = interp
    except Exception:
        pass


def torus_point(u, v, major=MAJOR, minor=MINOR, z=ROOT_Z):
    cu, su = math.cos(u), math.sin(u)
    cv, sv = math.cos(v), math.sin(v)
    x = (major + minor * cv) * cu
    y = (major + minor * cv) * su
    zz = z + minor * sv
    nx, ny, nz = cv * cu, cv * su, sv
    return Vector((x, y, zz)), Vector((nx, ny, nz)).normalized()


def build():
    random.seed(SEED)
    EXPORT.mkdir(parents=True, exist_ok=True)
    clear_scene()
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = END
    scene.frame_current = 48

    dough_mat = principled("Dough", (0.86, 0.62, 0.32), rough=0.72, spec=0.28, sss=0.18)
    frost_mat = principled("Frosting", (0.95, 0.28, 0.58), rough=0.18, spec=0.55, coat=0.55, trans=0.03)
    plate_mat = principled("Plate", (0.96, 0.94, 0.90), rough=0.18, spec=0.7, coat=0.25)
    table_mat = principled("Table", (0.91, 0.84, 0.76), rough=0.62, spec=0.2)
    sprinkle_colors = [
        (0.95, 0.20, 0.35),
        (0.20, 0.55, 0.95),
        (0.20, 0.78, 0.45),
        (0.98, 0.82, 0.18),
        (0.95, 0.95, 0.97),
        (0.62, 0.28, 0.90),
        (0.98, 0.45, 0.15),
    ]
    sprinkle_mats = [
        principled(f"Sprinkle_{i}", c, rough=0.35, spec=0.6, coat=0.2)
        for i, c in enumerate(sprinkle_colors)
    ]

    table = new_mesh_obj(bpy.ops.mesh.primitive_plane_add, "Table", size=9.0, location=(0.0, 0.0, -0.02))
    table.data.materials.clear()
    table.data.materials.append(table_mat)

    plate = new_mesh_obj(
        bpy.ops.mesh.primitive_cylinder_add,
        "Plate",
        vertices=64,
        radius=1.85,
        depth=0.08,
        location=(0.0, 0.0, PLATE_TOP - 0.04),
    )
    plate.data.materials.clear()
    plate.data.materials.append(plate_mat)
    shade_smooth(plate)

    rim = add_torus("PlateRim", 1.78, 0.045, PLATE_TOP + 0.02, segments=(64, 12))
    rim.data.materials.clear()
    rim.data.materials.append(plate_mat)
    shade_smooth(rim)

    root = bpy.data.objects.new("DonutRoot", None)
    bpy.context.collection.objects.link(root)
    root.empty_display_type = "PLAIN_AXES"
    root.location = (0.0, 0.0, ROOT_Z)

    dough = add_torus("Donut", MAJOR, MINOR, 0.0)
    dough.parent = root
    dough.data.materials.clear()
    dough.data.materials.append(dough_mat)
    shade_smooth(dough)

    frosting = frosting_from_torus(dough, "Frosting")
    frosting.parent = root
    frosting.location = (0.0, 0.0, 0.045)
    frosting.data.materials.clear()
    frosting.data.materials.append(frost_mat)
    apply_mods(frosting)
    shade_smooth(frosting)

    proto = new_mesh_obj(
        bpy.ops.mesh.primitive_cylinder_add,
        "SprinkleMesh",
        vertices=8,
        radius=0.028,
        depth=0.11,
        location=(0.0, 0.0, -20.0),
    )
    sprinkle_mesh = proto.data
    if not sprinkle_mesh.materials:
        sprinkle_mesh.materials.append(sprinkle_mats[0])
    bpy.data.objects.remove(proto, do_unlink=True)

    sprinkles = []
    for i in range(N_SPRINKLES):
        u = random.random() * math.tau
        v = 0.35 + random.random() * 1.05
        on_plate = i % 5 == 0
        obj = bpy.data.objects.new(f"Sprinkle_{i:02d}", sprinkle_mesh)
        bpy.context.collection.objects.link(obj)
        obj.material_slots[0].link = "OBJECT"
        obj.material_slots[0].material = sprinkle_mats[i % len(sprinkle_mats)]
        if on_plate:
            radius = 1.15 + random.random() * 0.45
            loc = Vector((math.cos(u) * radius, math.sin(u) * radius, PLATE_TOP + 0.03))
            n = Vector((0, 0, 1))
        else:
            loc, n = torus_point(u, v, major=MAJOR, minor=MINOR + 0.06, z=ROOT_Z + 0.05)
        quat = n.to_track_quat("Z", "Y")
        obj.rotation_euler = quat.to_euler()
        obj.rotation_euler.z += random.uniform(0, math.tau)
        obj["rest"] = list(loc)
        obj["start_frame"] = 40 + (i % 16)
        obj["flight"] = 12 + (i % 8)
        sprinkles.append(obj)

    # Animation: donut drop + squash
    rest = Vector((0.0, 0.0, ROOT_Z))
    key(root, "location", 1, (0, 0, 3.55), "BEZIER")
    key(root, "scale", 1, (1, 1, 1), "BEZIER")
    key(root, "location", 22, (0, 0, ROOT_Z + 0.01), "BEZIER")
    key(root, "scale", 22, (1.22, 1.22, 0.58), "BEZIER")
    key(root, "location", 28, (0, 0, ROOT_Z + 0.16), "BEZIER")
    key(root, "scale", 28, (0.93, 0.93, 1.14), "BEZIER")
    key(root, "location", 36, tuple(rest), "BEZIER")
    key(root, "scale", 36, (1, 1, 1), "BEZIER")
    key(root, "location", END, tuple(rest), "BEZIER")
    key(root, "scale", END, (1, 1, 1), "BEZIER")

    for obj in sprinkles:
        rest_loc = Vector(obj["rest"])
        start = int(obj["start_frame"])
        flight = int(obj["flight"])
        land = start + flight
        air = rest_loc + Vector((random.uniform(-0.08, 0.08), random.uniform(-0.08, 0.08), 2.4 + random.random() * 0.6))
        key(obj, "location", 1, tuple(air), "CONSTANT")
        key(obj, "scale", 1, (0, 0, 0), "CONSTANT")
        key(obj, "location", start, tuple(air), "BEZIER")
        key(obj, "scale", start, (1, 1, 1), "CONSTANT")
        key(obj, "location", land, tuple(rest_loc), "BEZIER")
        key(obj, "location", END, tuple(rest_loc), "BEZIER")
        obj.scale = (1, 1, 1)
        obj.location = rest_loc

    # Camera + lights
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 50
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (3.15, -3.35, 2.35)
    direction = Vector((0, 0, 0.35)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4.5
    sun.data.color = (1.0, 0.94, 0.88)
    sun.rotation_euler = (math.radians(48), math.radians(15), math.radians(35))
    bpy.context.collection.objects.link(sun)

    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "AREA"))
    fill.data.energy = 80
    fill.data.size = 2.4
    fill.data.color = (1.0, 0.82, 0.90)
    fill.location = (-2.2, 1.6, 2.4)
    fill.rotation_euler = (math.radians(55), 0, math.radians(-35))
    bpy.context.collection.objects.link(fill)

    rim_l = bpy.data.objects.new("RimLight", bpy.data.lights.new("RimLight", "AREA"))
    rim_l.data.energy = 40
    rim_l.data.size = 1.4
    rim_l.data.color = (0.85, 0.92, 1.0)
    rim_l.location = (1.4, 2.6, 1.8)
    bpy.context.collection.objects.link(rim_l)

    world = bpy.data.worlds.new("Studio")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.62, 0.42, 0.48, 1.0)
    bg.inputs[1].default_value = 0.55
    scene.world = world

    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        try:
            scene.render.engine = "BLENDER_EEVEE_NEXT"
        except TypeError:
            pass
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.fps = FPS
    scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = False
    scene.render.filepath = str(EXPORT / "preview")
    scene.render.image_settings.file_format = "PNG"

    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    return {
        "objects": [o.name for o in bpy.data.objects],
        "sprinkles": len(sprinkles),
        "blend": str(BLEND),
    }


def export_glb():
    path = str(EXPORT / "donut.glb")
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_animations=True,
        export_nla_strips=True,
        export_apply=True,
        export_cameras=False,
        export_lights=False,
    )
    return path


def render_still():
    scene = bpy.context.scene
    scene.frame_set(48)
    scene.render.filepath = str(EXPORT / "preview")
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    return str(EXPORT / "preview.png")


def render_mp4():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = END
    scene.render.filepath = str(EXPORT / "donut_drop")
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    bpy.ops.render.render(animation=True)
    return str(EXPORT / "donut_drop.mp4")


if __name__ == "__main__":
    info = build()
    glb = export_glb()
    still = render_still()
    print("BUILD_OK", info["blend"])
    print("GLB_OK", glb)
    print("STILL_OK", still)
    print("SPRINKLES", info["sprinkles"])

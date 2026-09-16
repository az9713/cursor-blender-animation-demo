"""Build a pepperoni pizza, plate, drop+squish animation, pineapple rain, and exports."""
from __future__ import annotations

import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
EXPORT = ROOT / "export"
BLEND = ROOT / "pizza.blend"

PIZZA_R = 1.28
CRUST_MAJOR = 1.22
CRUST_MINOR = 0.11
DOUGH_Z = 0.07
SAUCE_Z = 0.12
CHEESE_Z = 0.145
TOPPING_Z = 0.175
ROOT_Z = 0.18
PLATE_TOP = 0.07
FPS = 24
END = 96
SEED = 11
N_PEPPERONI = 18
N_PINEAPPLE = 28


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
    set_in(bsdf, ("Coat Roughness", "Clearcoat Roughness"), 0.16)
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
    scene = bpy.context.scene
    if scene.rigidbody_world:
        bpy.ops.rigidbody.world_remove()


def new_mesh_obj(op, name, **kwargs):
    bpy.ops.object.select_all(action="DESELECT")
    op(**kwargs)
    obj = bpy.context.active_object
    obj.name = name
    if obj.data:
        obj.data.name = name
    return obj


def apply_mods(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    for mod in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.select_set(False)


def bump_disc(obj, amount=0.012, seed=3):
    rng = random.Random(seed)
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        r = math.hypot(v.co.x, v.co.y)
        if r < 0.08:
            continue
        v.co.z += amount * (rng.random() - 0.4)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def rb_add(obj, body_type):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.rigidbody.object_add(type=body_type)
    obj.select_set(False)
    return obj.rigid_body


def setup_world(scene):
    if scene.rigidbody_world:
        bpy.ops.rigidbody.world_remove()
    bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    world.substeps_per_frame = 20
    world.solver_iterations = 25
    world.point_cache.frame_start = 1
    world.point_cache.frame_end = END
    scene.gravity = (0.0, 0.0, -9.81)
    return world


def setup_passive(obj, shape, restitution, friction=0.55):
    rb = rb_add(obj, "PASSIVE")
    rb.collision_shape = shape
    rb.restitution = restitution
    rb.friction = friction
    rb.use_margin = True
    rb.collision_margin = 0.004
    rb.mesh_source = "BASE"
    return rb


def bake_pineapple_physics(pineapple):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in pineapple:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = pineapple[0]
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for region in area.regions:
                if region.type != "WINDOW":
                    continue
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.ptcache.bake_all(bake=True)
                    bpy.ops.rigidbody.bake_to_keyframes(frame_start=1, frame_end=END, step=1)
                    return
    bpy.ops.ptcache.bake_all(bake=True)
    bpy.ops.rigidbody.bake_to_keyframes(frame_start=1, frame_end=END, step=1)


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


def build():
    random.seed(SEED)
    EXPORT.mkdir(parents=True, exist_ok=True)
    clear_scene()
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = END
    scene.frame_current = 48

    dough_mat = principled("Dough", (0.82, 0.58, 0.28), rough=0.78, spec=0.22, sss=0.12)
    crust_mat = principled("Crust", (0.62, 0.34, 0.14), rough=0.82, spec=0.18, sss=0.08)
    sauce_mat = principled("Sauce", (0.72, 0.12, 0.08), rough=0.42, spec=0.35, coat=0.12)
    cheese_mat = principled("Cheese", (0.96, 0.78, 0.28), rough=0.38, spec=0.48, coat=0.18, sss=0.1)
    pep_mat = principled("Pepperoni", (0.62, 0.10, 0.10), rough=0.48, spec=0.4, coat=0.08)
    plate_mat = principled("Plate", (0.96, 0.94, 0.90), rough=0.18, spec=0.7, coat=0.25)
    table_mat = principled("Table", (0.42, 0.26, 0.16), rough=0.7, spec=0.18)
    pine_colors = [
        (0.98, 0.82, 0.18),
        (0.95, 0.72, 0.12),
        (0.90, 0.62, 0.10),
        (0.99, 0.88, 0.32),
        (0.86, 0.55, 0.08),
    ]
    pine_mats = [
        principled(f"Pineapple_{i}", c, rough=0.55, spec=0.35, trans=0.04)
        for i, c in enumerate(pine_colors)
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

    rim = new_mesh_obj(
        bpy.ops.mesh.primitive_torus_add,
        "PlateRim",
        align="WORLD",
        location=(0.0, 0.0, PLATE_TOP + 0.02),
        major_segments=64,
        minor_segments=12,
        mode="MAJOR_MINOR",
        major_radius=1.78,
        minor_radius=0.045,
    )
    rim.data.materials.clear()
    rim.data.materials.append(plate_mat)
    shade_smooth(rim)

    root = bpy.data.objects.new("PizzaRoot", None)
    bpy.context.collection.objects.link(root)
    root.empty_display_type = "PLAIN_AXES"
    root.location = (0.0, 0.0, ROOT_Z)

    dough = new_mesh_obj(
        bpy.ops.mesh.primitive_cylinder_add,
        "Pizza",
        vertices=64,
        radius=PIZZA_R,
        depth=0.07,
        location=(0.0, 0.0, DOUGH_Z - ROOT_Z),
    )
    dough.parent = root
    dough.data.materials.clear()
    dough.data.materials.append(dough_mat)
    shade_smooth(dough)

    crust = new_mesh_obj(
        bpy.ops.mesh.primitive_torus_add,
        "Crust",
        align="WORLD",
        location=(0.0, 0.0, DOUGH_Z + 0.02 - ROOT_Z),
        major_segments=64,
        minor_segments=24,
        mode="MAJOR_MINOR",
        major_radius=CRUST_MAJOR,
        minor_radius=CRUST_MINOR,
    )
    crust.parent = root
    crust.data.materials.clear()
    crust.data.materials.append(crust_mat)
    shade_smooth(crust)

    sauce = new_mesh_obj(
        bpy.ops.mesh.primitive_cylinder_add,
        "Sauce",
        vertices=64,
        radius=1.08,
        depth=0.018,
        location=(0.0, 0.0, SAUCE_Z - ROOT_Z),
    )
    sauce.parent = root
    sauce.data.materials.clear()
    sauce.data.materials.append(sauce_mat)
    bump_disc(sauce, 0.004, 5)
    shade_smooth(sauce)

    cheese = new_mesh_obj(
        bpy.ops.mesh.primitive_cylinder_add,
        "Cheese",
        vertices=48,
        radius=1.05,
        depth=0.028,
        location=(0.0, 0.0, CHEESE_Z - ROOT_Z),
    )
    cheese.parent = root
    cheese.data.materials.clear()
    cheese.data.materials.append(cheese_mat)
    bump_disc(cheese, 0.016, 9)
    shade_smooth(cheese)

    pep_proto = new_mesh_obj(
        bpy.ops.mesh.primitive_cylinder_add,
        "PepperoniMesh",
        vertices=20,
        radius=0.16,
        depth=0.016,
        location=(0.0, 0.0, -20.0),
    )
    pep_mesh = pep_proto.data
    pep_mesh.materials.append(pep_mat)
    bpy.data.objects.remove(pep_proto, do_unlink=True)

    pepperoni = []
    placed = []
    attempts = 0
    while len(pepperoni) < N_PEPPERONI and attempts < 400:
        attempts += 1
        ang = random.random() * math.tau
        rad = math.sqrt(random.random()) * 0.92
        x, y = math.cos(ang) * rad, math.sin(ang) * rad
        if any(math.hypot(x - px, y - py) < 0.18 for px, py in placed) and random.random() > 0.35:
            continue
        obj = bpy.data.objects.new(f"Pepperoni_{len(pepperoni):02d}", pep_mesh)
        bpy.context.collection.objects.link(obj)
        obj.parent = root
        obj.location = (x, y, TOPPING_Z - ROOT_Z)
        obj.rotation_euler = (
            random.uniform(-0.12, 0.12),
            random.uniform(-0.12, 0.12),
            random.uniform(0, math.tau),
        )
        s = random.uniform(0.82, 1.18)
        obj.scale = (s, s, random.uniform(0.8, 1.2))
        pepperoni.append(obj)
        placed.append((x, y))

    pine_proto = new_mesh_obj(
        bpy.ops.mesh.primitive_cube_add,
        "PineappleMesh",
        size=0.12,
        location=(0.0, 0.0, -20.0),
    )
    bevel = pine_proto.modifiers.new("Bevel", "BEVEL")
    bevel.width = 0.018
    bevel.segments = 2
    apply_mods(pine_proto)
    pine_mesh = pine_proto.data
    if not pine_mesh.materials:
        pine_mesh.materials.append(pine_mats[0])
    bpy.data.objects.remove(pine_proto, do_unlink=True)

    pineapple = []
    for i in range(N_PINEAPPLE):
        obj = bpy.data.objects.new(f"Pineapple_{i:02d}", pine_mesh)
        bpy.context.collection.objects.link(obj)
        obj.material_slots[0].link = "OBJECT"
        obj.material_slots[0].material = pine_mats[i % len(pine_mats)]
        u = random.random() * math.tau
        on_plate = i % 6 == 0
        if on_plate:
            radius = 1.18 + random.random() * 0.32
        else:
            radius = math.sqrt(random.random()) * 0.88
        air = Vector((
            math.cos(u) * radius + random.uniform(-0.06, 0.06),
            math.sin(u) * radius + random.uniform(-0.06, 0.06),
            2.85 + random.random() * 0.7,
        ))
        obj.location = air
        obj.rotation_euler = (
            random.uniform(0, math.tau),
            random.uniform(0, math.tau),
            random.uniform(0, math.tau),
        )
        sx = random.uniform(0.7, 1.35)
        sy = random.uniform(0.55, 1.1)
        sz = random.uniform(0.55, 1.15)
        obj.scale = (sx, sy, sz)
        # Start falling while the pizza is still dropping so the site never
        # shows a hovering cloud after the pie is already on the plate.
        obj["start_frame"] = 8 + (i % 3)
        pineapple.append(obj)

    rest = Vector((0.0, 0.0, ROOT_Z))
    key(root, "location", 1, (0, 0, 3.55), "BEZIER")
    key(root, "scale", 1, (1, 1, 1), "BEZIER")
    key(root, "location", 22, (0, 0, ROOT_Z + 0.01), "BEZIER")
    key(root, "scale", 22, (1.18, 1.18, 0.62), "BEZIER")
    key(root, "location", 28, (0, 0, ROOT_Z + 0.14), "BEZIER")
    key(root, "scale", 28, (0.94, 0.94, 1.12), "BEZIER")
    key(root, "location", 36, tuple(rest), "BEZIER")
    key(root, "scale", 36, (1, 1, 1), "BEZIER")
    key(root, "location", END, tuple(rest), "BEZIER")
    key(root, "scale", END, (1, 1, 1), "BEZIER")

    setup_world(scene)
    setup_passive(table, "MESH", restitution=0.18, friction=0.7)
    setup_passive(plate, "CYLINDER", restitution=0.46, friction=0.5)
    setup_passive(rim, "MESH", restitution=0.4, friction=0.55)
    collider = new_mesh_obj(
        bpy.ops.mesh.primitive_cylinder_add,
        "PizzaCollider",
        vertices=48,
        radius=1.1,
        depth=0.12,
        location=(0.0, 0.0, 0.13),
    )
    collider.display_type = "WIRE"
    collider.hide_render = True
    setup_passive(collider, "CYLINDER", restitution=0.38, friction=0.6)

    for obj in pineapple:
        start = int(obj["start_frame"])
        rb = rb_add(obj, "ACTIVE")
        rb.collision_shape = "BOX"
        rb.mass = 0.045 * obj.scale.x * obj.scale.y * obj.scale.z
        rb.restitution = 0.62
        rb.friction = 0.48
        rb.linear_damping = 0.08
        rb.angular_damping = 0.22
        rb.use_margin = True
        rb.collision_margin = 0.003
        rb.use_deactivation = True
        rb.deactivate_linear_velocity = 0.12
        rb.deactivate_angular_velocity = 0.2
        rb.kinematic = True
        obj.keyframe_insert(data_path="location", frame=1)
        obj.keyframe_insert(data_path="rotation_euler", frame=1)
        obj.keyframe_insert(data_path="rigid_body.kinematic", frame=1)
        obj.keyframe_insert(data_path="location", frame=start)
        obj.keyframe_insert(data_path="rigid_body.kinematic", frame=start - 1)
        rb.kinematic = False
        obj.keyframe_insert(data_path="rigid_body.kinematic", frame=start)

    bake_pineapple_physics(pineapple)
    bpy.data.objects.remove(collider, do_unlink=True)

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 50
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (3.05, -3.15, 2.55)
    direction = Vector((0, 0, 0.22)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4.8
    sun.data.color = (1.0, 0.93, 0.82)
    sun.rotation_euler = (math.radians(50), math.radians(12), math.radians(40))
    bpy.context.collection.objects.link(sun)

    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "AREA"))
    fill.data.energy = 90
    fill.data.size = 2.6
    fill.data.color = (1.0, 0.78, 0.55)
    fill.location = (-2.2, 1.6, 2.4)
    fill.rotation_euler = (math.radians(55), 0, math.radians(-35))
    bpy.context.collection.objects.link(fill)

    rim_l = bpy.data.objects.new("RimLight", bpy.data.lights.new("RimLight", "AREA"))
    rim_l.data.energy = 45
    rim_l.data.size = 1.4
    rim_l.data.color = (1.0, 0.88, 0.7)
    rim_l.location = (1.4, 2.6, 1.8)
    bpy.context.collection.objects.link(rim_l)

    world = bpy.data.worlds.new("Studio")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.42, 0.18, 0.10, 1.0)
    bg.inputs[1].default_value = 0.5
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
        "pepperoni": len(pepperoni),
        "pineapple": len(pineapple),
        "blend": str(BLEND),
    }


def export_glb():
    path = str(EXPORT / "pizza.glb")
    # Blender 5 slotted actions do not round-trip through the default
    # ACTIONS exporter; sample the scene so the GLB matches viewport playback.
    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_animations=True,
        export_animation_mode="SCENE",
        export_force_sampling=True,
        export_frame_range=True,
        export_anim_slide_to_zero=True,
        export_optimize_animation_keep_anim_object=True,
        export_merge_animation="NLA_TRACK",
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


if __name__ == "__main__":
    info = build()
    glb = export_glb()
    still = render_still()
    print("BUILD_OK", info["blend"])
    print("GLB_OK", glb)
    print("STILL_OK", still)
    print("PEPPERONI", info["pepperoni"])
    print("PINEAPPLE", info["pineapple"])

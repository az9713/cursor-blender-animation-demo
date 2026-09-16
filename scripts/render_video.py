import bpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORT = ROOT / "export"
out = EXPORT / "pizza_drop"
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 96
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.fps = 24
scene.render.filepath = str(out)
try:
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
except TypeError:
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str((EXPORT / "frames") / "frame")
print("FORMAT", scene.render.image_settings.file_format)
print("ENGINE", scene.render.engine)
bpy.ops.render.render(animation=True)
print("VIDEO_OK")

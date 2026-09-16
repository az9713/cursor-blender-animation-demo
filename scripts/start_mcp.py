"""Enable the Blender MCP addon and start the TCP server on port 9876."""
import addon_utils
import bpy

addon_utils.enable("blender_mcp")


def _start():
    try:
        bpy.ops.blendermcp.start_server()
        print("MCP_SERVER_STARTED")
    except Exception as exc:
        print("MCP_START_FAIL", exc)
    return None


bpy.app.timers.register(_start, first_interval=0.4)

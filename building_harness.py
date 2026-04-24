import io
import os
import math
import base64
import subprocess
from pydantic_ai import Agent, RunContext
from rmf_config import RMF_BASE, RmfDeps, make_client, model
from PIL import Image, ImageDraw

agent = Agent(
    model,
    deps_type=RmfDeps,
    system_prompt=(
        "You are an RMF building operator. Use the available tools to render floor plans. Be concise."
    ),
)


@agent.tool
def render_level(ctx: RunContext[RmfDeps], level_name: str) -> str:
    """
    Render the floor plan image for a specific level with doors and lifts overlaid.
    Saves to .states/ and opens it. Returns the file path.
    """
    resp = ctx.deps.client.get(f"{RMF_BASE}/building_map")
    resp.raise_for_status()
    bmap = resp.json()

    level = next((l for l in bmap.get("levels", []) if l["name"] == level_name), None)
    if level is None:
        return f"Level '{level_name}' not found. Available: {[l['name'] for l in bmap['levels']]}"

    images = level.get("images", [])
    if not images:
        return f"Level '{level_name}' has no floor plan image."

    img_data = images[0]
    data = img_data["data"]
    if isinstance(data, str) and data.startswith("http"):
        raw = ctx.deps.client.get(data).content
    elif isinstance(data, str):
        raw = base64.b64decode(data)
    else:
        raw = bytes(data)

    scale = img_data["scale"]
    x_offset = img_data["x_offset"]
    y_offset = img_data["y_offset"]

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    def world_to_pixel(wx, wy):
        return ((wx - x_offset) / scale, (y_offset - wy) / scale)

    # draw waypoints from all nav_graphs (yellow boxes, same as rmf-web)
    for graph in level.get("nav_graphs", []):
        for vertex in graph.get("vertices", []):
            px, py = world_to_pixel(vertex["x"], vertex["y"])
            r = 4
            draw.rectangle([px - r, py - r, px + r, py + r], fill=(255, 220, 0, 180))
            if vertex.get("name"):
                draw.text((px + r + 2, py - r), vertex["name"], fill=(255, 220, 0, 255))

    for door in level.get("doors", []):
        p1 = world_to_pixel(door["v1_x"], door["v1_y"])
        p2 = world_to_pixel(door["v2_x"], door["v2_y"])
        draw.line([p1, p2], fill=(255, 80, 80, 255), width=4)
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        draw.text((mx + 2, my + 2), door["name"], fill=(255, 80, 80, 255))

    for lift in bmap.get("lifts", []):
        if level_name not in lift.get("levels", []):
            continue
        px, py = world_to_pixel(lift["ref_x"], lift["ref_y"])
        yaw = lift.get("ref_yaw", 0)
        corners_world = [
            ( lift["width"] / 2,  lift["depth"] / 2),
            (-lift["width"] / 2,  lift["depth"] / 2),
            (-lift["width"] / 2, -lift["depth"] / 2),
            ( lift["width"] / 2, -lift["depth"] / 2),
        ]
        def rotate(cx, cy, angle):
            c, s = math.cos(angle), math.sin(angle)
            return (cx * c - cy * s + lift["ref_x"], cx * s + cy * c + lift["ref_y"])
        corners_px = [world_to_pixel(*rotate(cx, cy, yaw)) for cx, cy in corners_world]
        draw.polygon(corners_px, outline=(80, 160, 255, 255), fill=(80, 160, 255, 60))
        draw.text((px + 2, py + 2), lift["name"], fill=(80, 160, 255, 255))

    os.makedirs(".states", exist_ok=True)
    out_path = f".states/rmf_{level_name}.png"
    img.save(out_path)
    return f"Rendered to {out_path}"


if __name__ == "__main__":
    with make_client() as client:
        deps = RmfDeps(client=client)
        history = []
        print("RMF Building Harness ready. Ctrl+C to exit.\n")
        while True:
            try:
                user_input = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not user_input:
                continue
            result = agent.run_sync(user_input, deps=deps, message_history=history)
            print(f"Agent: {result.output}\n")
            history = result.all_messages()

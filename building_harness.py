import io
import os
import json
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
        "You are an RMF building operator. Use the available tools to render floor plans "
        "and query waypoint annotations. Be concise.\n"
        "When answering questions about waypoints, prefer explicit facts from annotation "
        "descriptions. Only fall back to inferring from waypoint names or other annotation "
        "context if no relevant annotation exists."
    ),
)


@agent.tool
def query_waypoints(ctx: RunContext[RmfDeps], level_name: str) -> list[dict]:
    """
    Return all named waypoints for a level with text descriptions from
    .states/<world>_<level>.annotations.json. Render the level first to generate the file.
    """
    resp = ctx.deps.client.get(f"{RMF_BASE}/building_map")
    resp.raise_for_status()
    bmap = resp.json()

    world_name = bmap.get("name", "world")
    ann_path = f".states/{world_name}_{level_name}.annotations.json"
    if not os.path.exists(ann_path):
        return [{"error": f"Annotation file {ann_path} not found. Run render_level('{level_name}') first."}]

    with open(ann_path) as f:
        annotations = json.load(f)

    level_ann = annotations.get(level_name, {})
    return [{"name": wp, "description": desc} for wp, desc in level_ann.items()]


@agent.tool
def propose_waypoint_update(ctx: RunContext[RmfDeps], level_name: str, waypoint_name: str, fact: str) -> dict:
    """
    Propose appending a fact to a waypoint annotation. Does NOT write anything.
    Returns the before/after for human review. Call confirm_waypoint_update to apply.
    """
    resp = ctx.deps.client.get(f"{RMF_BASE}/building_map")
    resp.raise_for_status()
    bmap = resp.json()

    world_name = bmap.get("name", "world")
    ann_path = f".states/{world_name}_{level_name}.annotations.json"
    if not os.path.exists(ann_path):
        return {"error": f"Annotation file {ann_path} not found. Run render_level('{level_name}') first."}

    with open(ann_path) as f:
        annotations = json.load(f)

    level_ann = annotations.get(level_name, {})
    existing = level_ann.get(waypoint_name)
    if existing is None:
        return {"error": f"Waypoint '{waypoint_name}' not found in level '{level_name}'."}

    new_desc = f"{existing}. {fact}".lstrip(". ") if existing else fact
    return {
        "level": level_name,
        "waypoint": waypoint_name,
        "before": existing,
        "after": new_desc,
    }


@agent.tool
def confirm_waypoint_update(ctx: RunContext[RmfDeps], level_name: str, waypoint_name: str, new_desc: str) -> str:
    """
    Write a confirmed waypoint annotation update to file.
    Call this only after the human has approved the proposal from propose_waypoint_update.
    """
    resp = ctx.deps.client.get(f"{RMF_BASE}/building_map")
    resp.raise_for_status()
    bmap = resp.json()

    world_name = bmap.get("name", "world")
    ann_path = f".states/{world_name}_{level_name}.annotations.json"
    if not os.path.exists(ann_path):
        return f"Annotation file {ann_path} not found."

    with open(ann_path) as f:
        annotations = json.load(f)

    annotations.setdefault(level_name, {})[waypoint_name] = new_desc

    with open(ann_path, "w") as f:
        json.dump(annotations, f, indent=2)

    return f"Updated '{waypoint_name}' on {level_name}: \"{new_desc}\""


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
        for door in lift.get("doors", []):
            p1 = world_to_pixel(door["v1_x"], door["v1_y"])
            p2 = world_to_pixel(door["v2_x"], door["v2_y"])
            draw.line([p1, p2], fill=(80, 220, 255, 255), width=4)
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            draw.text((mx + 2, my + 2), door["name"], fill=(80, 220, 255, 255))

    os.makedirs(".states", exist_ok=True)
    world_name = bmap.get("name", "world")
    out_path = f".states/{world_name}_{level_name}.png"
    ann_path = f".states/{world_name}_{level_name}.annotations.json"
    img.save(out_path)

    # collect named waypoints from nav graphs
    named_waypoints = [
        v["name"]
        for graph in level.get("nav_graphs", [])
        for v in graph.get("vertices", [])
        if v.get("name")
    ]

    named_set = set(named_waypoints)

    if not os.path.exists(ann_path):
        annotations = {level_name: {wp: "" for wp in named_waypoints}}
        removed = []
    else:
        with open(ann_path) as f:
            annotations = json.load(f)
        level_ann = annotations.setdefault(level_name, {})
        # add missing
        for wp in named_waypoints:
            level_ann.setdefault(wp, "")
        # remove stale
        removed = [wp for wp in list(level_ann) if wp not in named_set]
        for wp in removed:
            del level_ann[wp]

    with open(ann_path, "w") as f:
        json.dump(annotations, f, indent=2)

    new_count = sum(1 for wp in named_waypoints if not annotations[level_name].get(wp))
    removed_str = f", removed stale: {removed}" if removed else ""
    return f"Rendered to {out_path}, annotations at {ann_path} ({new_count} empty entries{removed_str})"


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

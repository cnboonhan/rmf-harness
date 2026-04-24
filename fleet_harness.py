import os
import base64
from pydantic_ai import Agent, RunContext
from rmf_config import RMF_BASE, RmfDeps, make_client, model

agent = Agent(
    model,
    deps_type=RmfDeps,
    system_prompt=(
        "You are an RMF fleet operator. Use the available tools to inspect fleets, "
        "send robots to waypoints, and fetch robot camera views. Be concise.\n"
        "For queries about what a robot sees, its view, its camera, or its ego perspective: "
        "call query_robot_camera. If the fleet name is not given, call list_fleets first "
        "to find which fleet the robot belongs to. Default camera_id is 'camera_front'."
    ),
)


@agent.tool
def list_fleets(ctx: RunContext[RmfDeps]) -> list[dict]:
    """List all fleets and their robots with current location and status."""
    resp = ctx.deps.client.get(f"{RMF_BASE}/fleets")
    resp.raise_for_status()
    fleets = resp.json()
    summary = []
    for fleet in fleets:
        robots = {}
        for name, robot in (fleet.get("robots") or {}).items():
            loc = robot.get("location") or {}
            robots[name] = {
                "status": robot.get("status"),
                "map": loc.get("map"),
                "x": loc.get("x"),
                "y": loc.get("y"),
                "task_id": robot.get("task_id"),
            }
        summary.append({"fleet": fleet["name"], "robots": robots})
    return summary


@agent.tool
def move_robot_to_waypoint(
    ctx: RunContext[RmfDeps],
    fleet_name: str,
    waypoint: str,
) -> dict:
    """
    Dispatch a patrol task (1 round, 1 place) to move a robot to a waypoint.
    fleet_name: name of the fleet to assign the task to.
    waypoint: name of the destination waypoint.
    """
    body = {
        "type": "dispatch_task_request",
        "request": {
            "category": "patrol",
            "description": {"places": [waypoint], "rounds": 1},
            "fleet_name": fleet_name,
        },
    }
    resp = ctx.deps.client.post(f"{RMF_BASE}/tasks/dispatch_task", json=body)
    resp.raise_for_status()
    return resp.json()


@agent.tool
def query_robot_camera(
    ctx: RunContext[RmfDeps],
    fleet_name: str,
    robot_name: str,
    camera_id: str = "camera_front",
) -> dict:
    """
    Fetch the latest camera frame for a robot from RMF RIO and save it to .states/.
    Returns the saved file path and frame metadata (timestamp, size).
    RIO type convention: {fleet_name}/{robot_name}/{camera_id}
    """
    rio_type = f"{fleet_name}/{robot_name}/{camera_id}"
    resp = ctx.deps.client.get(f"{RMF_BASE}/rios?type={rio_type}")
    resp.raise_for_status()
    rios = resp.json()
    if not rios:
        return {"error": f"No RIO data found for type '{rio_type}'"}

    rio = rios[0] if isinstance(rios, list) else rios
    data = rio.get("data", {})
    b64 = data.get("base64")
    if not b64:
        return {"error": "RIO entry has no base64 image data", "rio": rio}

    jpeg_bytes = base64.b64decode(b64)
    os.makedirs(".states", exist_ok=True)
    filename = f"{fleet_name}_{robot_name}_{camera_id}.jpg"
    out_path = f".states/{filename}"
    with open(out_path, "wb") as f:
        f.write(jpeg_bytes)

    return {
        "path": out_path,
        "timestamp": data.get("timestamp"),
        "width": data.get("width"),
        "height": data.get("height"),
        "size_bytes": len(jpeg_bytes),
    }


if __name__ == "__main__":
    with make_client() as client:
        deps = RmfDeps(client=client)
        history = []
        print("RMF Fleet Harness ready. Ctrl+C to exit.\n")
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

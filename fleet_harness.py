from pydantic_ai import Agent, RunContext
from rmf_config import RMF_BASE, RmfDeps, make_client, model

agent = Agent(
    model,
    deps_type=RmfDeps,
    system_prompt=(
        "You are an RMF fleet operator. Use the available tools to inspect fleets "
        "and send robots to waypoints. Be concise."
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

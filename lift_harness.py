from pydantic_ai import Agent, RunContext
from rmf_config import RMF_BASE, RmfDeps, make_client, model

REQUEST_TYPES = {0: "END_SESSION", 1: "AGV_MODE", 2: "HUMAN_MODE"}
DOOR_MODES    = {0: "CLOSED", 2: "OPEN"}
MOTION_STATES = {0: "UNKNOWN", 1: "STOPPED", 2: "UP", 3: "DOWN", 4: "UNINITIALIZED"}

agent = Agent(
    model,
    deps_type=RmfDeps,
    system_prompt=(
        "You are an RMF building operator. Use the available tools to inspect "
        "and control lifts. Be concise."
    ),
)


@agent.tool
def list_lifts(ctx: RunContext[RmfDeps]) -> list[dict]:
    """List all lifts in the building."""
    resp = ctx.deps.client.get(f"{RMF_BASE}/lifts")
    resp.raise_for_status()
    return resp.json()


@agent.tool
def get_lift_state(ctx: RunContext[RmfDeps], lift_name: str) -> dict:
    """Get current state of a specific lift."""
    resp = ctx.deps.client.get(f"{RMF_BASE}/lifts/{lift_name}/state")
    resp.raise_for_status()
    data = resp.json()
    data["motion_state_label"] = MOTION_STATES.get(data.get("motion_state"), "UNKNOWN")
    data["door_state_label"] = DOOR_MODES.get(data.get("door_state"), "UNKNOWN")
    return data


@agent.tool
def request_lift(
    ctx: RunContext[RmfDeps],
    lift_name: str,
    destination: str,
    request_type: int,
    door_mode: int,
) -> str:
    """
    Send a request to a lift.
    request_type: 0=END_SESSION, 1=AGV_MODE, 2=HUMAN_MODE
    door_mode:    0=CLOSED, 2=OPEN
    destination:  floor name e.g. 'L1', 'L2'
    """
    resp = ctx.deps.client.post(
        f"{RMF_BASE}/lifts/{lift_name}/request",
        json={"request_type": request_type, "door_mode": door_mode, "destination": destination},
    )
    resp.raise_for_status()
    return (
        f"Requested {lift_name} -> {destination} "
        f"({REQUEST_TYPES.get(request_type, request_type)}, "
        f"door={DOOR_MODES.get(door_mode, door_mode)})"
    )


if __name__ == "__main__":
    with make_client() as client:
        deps = RmfDeps(client=client)
        history = []
        print("RMF Lift Harness ready. Ctrl+C to exit.\n")
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

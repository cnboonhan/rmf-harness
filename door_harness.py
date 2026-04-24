from pydantic_ai import Agent, RunContext
from rmf_config import RMF_BASE, RmfDeps, make_client, model

DOOR_MODES = {0: "CLOSED", 1: "MOVING", 2: "OPEN", 3: "OFFLINE", 4: "UNKNOWN"}

agent = Agent(
    model,
    deps_type=RmfDeps,
    system_prompt=(
        "You are an RMF building operator. Use the available tools to inspect "
        "and control doors. Be concise."
    ),
)


@agent.tool
def list_doors(ctx: RunContext[RmfDeps]) -> list[dict]:
    """List all doors in the building."""
    resp = ctx.deps.client.get(f"{RMF_BASE}/doors")
    resp.raise_for_status()
    return resp.json()


@agent.tool
def get_door_state(ctx: RunContext[RmfDeps], door_name: str) -> dict:
    """Get current state of a specific door."""
    resp = ctx.deps.client.get(f"{RMF_BASE}/doors/{door_name}/state")
    resp.raise_for_status()
    data = resp.json()
    data["mode_label"] = DOOR_MODES.get(data.get("current_mode", {}).get("value"), "UNKNOWN")
    return data


@agent.tool
def request_door(ctx: RunContext[RmfDeps], door_name: str, mode: int) -> str:
    """
    Send open/close request to a door.
    mode: 0=CLOSED, 2=OPEN
    """
    resp = ctx.deps.client.post(
        f"{RMF_BASE}/doors/{door_name}/request",
        json={"mode": mode},
    )
    resp.raise_for_status()
    return f"Requested {door_name} -> {DOOR_MODES.get(mode, str(mode))}"


if __name__ == "__main__":
    with make_client() as client:
        deps = RmfDeps(client=client)
        history = []
        print("RMF Door Harness ready. Ctrl+C to exit.\n")
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

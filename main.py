import os
from pydantic_ai import Agent, RunContext
from rmf_config import RmfDeps, make_client, model
import door_harness
import lift_harness
import fleet_harness
import building_harness

VERBOSE = os.environ.get("VERBOSE", "1") != "0"

PLANNER = Agent(
    model,
    deps_type=RmfDeps,
    system_prompt=(
        "You are an RMF orchestrator. When given a goal, output ONLY a numbered plan "
        "of sub-agent calls needed to achieve it. Format each step as:\n"
        "  N. [agent] instruction\n"
        "where agent is one of: door, lift, fleet, building.\n"
        "Do not execute anything. Do not call any tools. Just list the steps."
    ),
)

agent = Agent(
    model,
    deps_type=RmfDeps,
    system_prompt=(
        "You are an RMF orchestrator. Achieve multi-step building logistics goals by "
        "delegating to specialized sub-agents: door, lift, fleet, building. Be concise.\n"
        "For waypoint annotation updates: always call propose_waypoint_update first, "
        "show the before/after to the user, and only call confirm_waypoint_update after "
        "the user explicitly approves."
    ),
)


def _verbose(direction: str, agent_name: str, msg: str):
    if VERBOSE:
        print(f"  {direction} [{agent_name}] {msg}")


@agent.tool
def ask_door_agent(ctx: RunContext[RmfDeps], instruction: str) -> str:
    """Delegate a door-related instruction to the door agent."""
    _verbose("→", "door", instruction)
    out = door_harness.agent.run_sync(instruction, deps=ctx.deps).output
    _verbose("←", "door", out)
    return out


@agent.tool
def ask_lift_agent(ctx: RunContext[RmfDeps], instruction: str) -> str:
    """Delegate a lift-related instruction to the lift agent."""
    _verbose("→", "lift", instruction)
    out = lift_harness.agent.run_sync(instruction, deps=ctx.deps).output
    _verbose("←", "lift", out)
    return out


@agent.tool
def ask_fleet_agent(ctx: RunContext[RmfDeps], instruction: str) -> str:
    """Delegate a robot/fleet instruction to the fleet agent."""
    _verbose("→", "fleet", instruction)
    out = fleet_harness.agent.run_sync(instruction, deps=ctx.deps).output
    _verbose("←", "fleet", out)
    return out


@agent.tool
def ask_building_agent(ctx: RunContext[RmfDeps], instruction: str) -> str:
    """Delegate a building map/floor plan instruction to the building agent."""
    _verbose("→", "building", instruction)
    out = building_harness.agent.run_sync(instruction, deps=ctx.deps).output
    _verbose("←", "building", out)
    return out


if __name__ == "__main__":
    with make_client() as client:
        deps = RmfDeps(client=client)
        history = []
        print("RMF Orchestrator ready. Ctrl+C to exit.")
        print("VERBOSE =", VERBOSE, " (set VERBOSE=0 to disable)\n")
        while True:
            try:
                user_input = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not user_input:
                continue

            # phase 1: plan
            plan_result = PLANNER.run_sync(user_input, deps=deps)
            print(f"\nPlan:\n{plan_result.output}\n")

            try:
                confirm = input("Execute? [y/N] ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                break
            if confirm != "y":
                print("Cancelled.\n")
                continue

            # phase 2: execute
            result = agent.run_sync(user_input, deps=deps, message_history=history)
            print(f"\nAgent: {result.output}\n")
            history = result.all_messages()

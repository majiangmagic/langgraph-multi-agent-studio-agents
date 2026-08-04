"""Runtime constants and node factory for the harness planner agent."""

from app.agents.harness.harness_planner.nodes import HarnessPlannerNode

HARNESS_PLANNER_AGENT_NAME = "harness_planner"
HARNESS_PLANNER_ENTRYPOINT = "harness_planner"


def create_harness_planner_node() -> HarnessPlannerNode:
    """Create the harness planner node."""

    return HarnessPlannerNode()

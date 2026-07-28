"""Runtime constants and node factory for the official supervisor Agent example."""

from app.agents.official_supervisor.nodes import SupervisorExampleNode

OFFICIAL_SUPERVISOR_AGENT_NAME = "official_supervisor"
OFFICIAL_SUPERVISOR_ENTRYPOINT = "official_supervisor"


def create_official_supervisor_node() -> SupervisorExampleNode:
    """Create the non-runnable supervisor example node."""

    return SupervisorExampleNode()

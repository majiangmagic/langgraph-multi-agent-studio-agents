"""Runtime constants and node factory for the official supervisor agent."""

from app.agents.official_supervisor.nodes import OfficialSupervisorNode

OFFICIAL_SUPERVISOR_AGENT_NAME = "official_supervisor"
OFFICIAL_SUPERVISOR_ENTRYPOINT = "official_supervisor"


def create_official_supervisor_node():
    """Create the official supervisor node callable."""

    return OfficialSupervisorNode()

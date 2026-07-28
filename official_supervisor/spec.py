"""Declarative spec for the official_supervisor agent."""

from langgraph.graph import END

from app.runtime.langgraph.agent_definition import (
    AgentDefinition,
    AgentEdgeSpec,
    AgentNodeSpec,
)
from app.agents.official_supervisor.nodes import official_supervisor_node
from app.agents.official_supervisor.state import SupervisorState

OFFICIAL_SUPERVISOR_AGENT_NAME = "official_supervisor"
OFFICIAL_SUPERVISOR_ENTRYPOINT = "official_supervisor"


def create_official_supervisor_node():
    """Create the official supervisor node callable."""

    return official_supervisor_node


AGENT_DEFINITION = AgentDefinition(
    name=OFFICIAL_SUPERVISOR_AGENT_NAME,
    state_schema=SupervisorState,
    entrypoint=OFFICIAL_SUPERVISOR_ENTRYPOINT,
    nodes=[
        AgentNodeSpec(
            name="official_supervisor",
            factory=create_official_supervisor_node,
        ),
    ],
    edges=[
        AgentEdgeSpec(source="official_supervisor", target=END),
    ],
)

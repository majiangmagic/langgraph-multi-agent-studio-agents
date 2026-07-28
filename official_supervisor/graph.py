"""Native LangGraph graph for the official supervisor agent."""

from langgraph.graph import END, StateGraph

from app.agents.official_supervisor.nodes import OfficialSupervisorNode
from app.agents.official_supervisor.state import SupervisorState
from app.agents.registry import agent_registry

OFFICIAL_SUPERVISOR_AGENT_NAME = "official_supervisor"


class OfficialSupervisorGraph:
    """Object-oriented graph builder using native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(SupervisorState)
        workflow.add_node("official_supervisor", OfficialSupervisorNode())
        workflow.add_edge("official_supervisor", END)
        workflow.set_entry_point("official_supervisor")
        return workflow.compile()


def create_graph():
    """Create the official supervisor agent graph."""

    return OfficialSupervisorGraph().build_graph()


create_official_supervisor_graph = create_graph
agent_registry.register(OFFICIAL_SUPERVISOR_AGENT_NAME, create_graph)

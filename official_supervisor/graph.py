"""Native LangGraph skeleton for the official supervisor Agent example."""

from langgraph.graph import END, StateGraph

from app.agents.official_supervisor.nodes import SupervisorExampleNode
from app.agents.official_supervisor.state import SupervisorState
from app.agents.registry import agent_registry

OFFICIAL_SUPERVISOR_AGENT_NAME = "official_supervisor"


class OfficialSupervisorGraph:
    """Graph skeleton retained as a non-runnable example."""

    def build_graph(self):
        workflow = StateGraph(SupervisorState)
        workflow.add_node("official_supervisor", SupervisorExampleNode())
        workflow.add_edge("official_supervisor", END)
        workflow.set_entry_point("official_supervisor")
        return workflow.compile()


def create_graph():
    """Create the non-runnable official supervisor example graph."""

    return OfficialSupervisorGraph().build_graph()


create_official_supervisor_graph = create_graph
agent_registry.register(OFFICIAL_SUPERVISOR_AGENT_NAME, create_graph)

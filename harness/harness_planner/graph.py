"""Native LangGraph graph for the harness planner agent."""

from langgraph.graph import END, StateGraph

from app.agents.harness.harness_planner.nodes import HarnessPlannerNode
from app.agents.harness.harness_planner.spec import HARNESS_PLANNER_AGENT_NAME
from app.agents.harness.harness_planner.state import HarnessPlannerState
from app.agents.registry import agent_registry


class HarnessPlannerGraph:
    """Graph that analyzes an existing project and updates planning docs."""

    def build_graph(self):
        workflow = StateGraph(HarnessPlannerState)
        workflow.add_node(HARNESS_PLANNER_AGENT_NAME, HarnessPlannerNode())
        workflow.add_edge(HARNESS_PLANNER_AGENT_NAME, END)
        workflow.set_entry_point(HARNESS_PLANNER_AGENT_NAME)
        return workflow.compile()


def create_graph():
    """Create the harness planner agent graph."""

    return HarnessPlannerGraph().build_graph()


agent_registry.register(HARNESS_PLANNER_AGENT_NAME, create_graph)

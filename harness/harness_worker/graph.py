"""Native LangGraph graph for the Harness worker agent."""

from langgraph.graph import END, StateGraph

from app.agents.harness.harness_worker.nodes import HarnessWorkerNode
from app.agents.harness.harness_worker.spec import HARNESS_WORKER_AGENT_NAME
from app.agents.harness.harness_worker.state import HarnessWorkerState
from app.agents.registry import agent_registry


class HarnessWorkerGraph:
    """Graph that executes the current work described by PROGRESS.md."""

    def build_graph(self):
        workflow = StateGraph(HarnessWorkerState)
        workflow.add_node(HARNESS_WORKER_AGENT_NAME, HarnessWorkerNode())
        workflow.add_edge(HARNESS_WORKER_AGENT_NAME, END)
        workflow.set_entry_point(HARNESS_WORKER_AGENT_NAME)
        return workflow.compile()


def create_graph():
    """Create the Harness worker agent graph."""

    return HarnessWorkerGraph().build_graph()


agent_registry.register(HARNESS_WORKER_AGENT_NAME, create_graph)

"""Native LangGraph graph for the Harness checker agent."""

from langgraph.graph import END, StateGraph

from app.agents.harness.harness_checker.nodes import (
    FunctionalityCheckerNode,
    GitCheckpointCreatorNode,
    DocumentCheckerNode,
)
from app.agents.harness.harness_checker.spec import HARNESS_CHECKER_AGENT_NAME
from app.agents.harness.harness_checker.state import HarnessCheckerState
from app.agents.registry import agent_registry


class HarnessCheckerGraph:
    """Graph that validates the feature, checks Markdown, and creates a checkpoint."""

    def build_graph(self):
        workflow = StateGraph(HarnessCheckerState)
        workflow.add_node("functionality_checker", FunctionalityCheckerNode())
        workflow.add_node("document_checker", DocumentCheckerNode())
        workflow.add_node("git_checkpoint_creator", GitCheckpointCreatorNode())
        workflow.add_conditional_edges(
            "functionality_checker",
            route_after_functionality_check,
            {"check_documents": "document_checker", "remake": END},
        )
        workflow.add_conditional_edges(
            "document_checker",
            route_after_document_check,
            {"archive": "git_checkpoint_creator", "remake": END},
        )
        workflow.add_edge("git_checkpoint_creator", END)
        workflow.set_entry_point("functionality_checker")
        return workflow.compile()


def route_after_functionality_check(state: HarnessCheckerState) -> str:
    """Run all Harness document checks after functionality validation passes."""

    return "check_documents" if state.get("status") == "checking" else "remake"


def route_after_document_check(state: HarnessCheckerState) -> str:
    """Archive only when every check.py validation passes."""

    return "archive" if state.get("status") == "verified" else "remake"


def create_graph():
    """Create the Harness checker agent graph."""

    return HarnessCheckerGraph().build_graph()


agent_registry.register(HARNESS_CHECKER_AGENT_NAME, create_graph)

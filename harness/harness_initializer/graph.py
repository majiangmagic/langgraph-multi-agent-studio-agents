"""Native LangGraph graph for the harness initializer agent."""

from langgraph.graph import END, StateGraph

from app.agents.harness.harness_initializer.nodes import (
    EnvironmentCheckerNode,
    GitRepoCreatorNode,
    GitRepoRefresherNode,
    MarkdownCreatorNode,
)
from app.agents.harness.harness_initializer.state import HarnessInitializerState
from app.agents.registry import agent_registry

HARNESS_INITIALIZER_AGENT_NAME = "harness_initializer"


class HarnessInitializerGraph:
    """Graph that bootstraps a fresh project with Harness support files."""

    def build_graph(self):
        workflow = StateGraph(HarnessInitializerState)
        workflow.add_node("environment_checker", EnvironmentCheckerNode())
        workflow.add_node("markdown_creator", MarkdownCreatorNode())
        workflow.add_node("git_repo_creator", GitRepoCreatorNode())
        workflow.add_node("git_repo_refresher", GitRepoRefresherNode())
        workflow.add_conditional_edges(
            "environment_checker",
            route_after_environment_check,
            {
                "markdown_creator": "markdown_creator",
                "refresh_git_repository": "git_repo_refresher",
            },
        )
        workflow.add_edge("markdown_creator", "git_repo_creator")
        workflow.add_edge("git_repo_creator", "git_repo_refresher")
        workflow.add_edge("git_repo_refresher", END)
        workflow.set_entry_point("environment_checker")
        return workflow.compile()



def route_after_environment_check(state: HarnessInitializerState) -> str:
    """Send fresh projects through initialization and existing ones to planning."""

    return "markdown_creator" if state.get("should_initialize") else "refresh_git_repository"



def create_graph():
    """Create the harness initializer agent graph."""

    return HarnessInitializerGraph().build_graph()


agent_registry.register(HARNESS_INITIALIZER_AGENT_NAME, create_graph)

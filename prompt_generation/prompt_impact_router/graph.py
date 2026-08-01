"""Native LangGraph graph for the prompt_impact_router agent."""

from langgraph.graph import END, StateGraph

from app.agents.prompt_generation.prompt_impact_router.state import PromptImpactRouterState
from app.agents.prompt_generation.prompt_impact_router.nodes import RouteImpactNode
PROMPT_IMPACT_ROUTER_AGENT_NAME = "prompt_impact_router"

from app.agents.registry import agent_registry


class PromptImpactRouterGraph:
    """Build the prompt_impact_router graph with native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(PromptImpactRouterState)
        workflow.add_node("route_impact", RouteImpactNode())
        workflow.add_edge("route_impact", END)
        workflow.set_entry_point("route_impact")
        return workflow.compile()


def create_graph():
    """Create the prompt_impact_router agent graph."""

    return PromptImpactRouterGraph().build_graph()


agent_registry.register(PROMPT_IMPACT_ROUTER_AGENT_NAME, create_graph)

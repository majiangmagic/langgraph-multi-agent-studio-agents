"""Native LangGraph graph for the visual_semantic_resolver agent."""

from langgraph.graph import END, StateGraph

from app.agents.prompt_generation.visual_semantic_resolver.state import VisualSemanticResolverState
from app.agents.prompt_generation.visual_semantic_resolver.nodes import PrepareContextNode
from app.agents.prompt_generation.visual_semantic_resolver.nodes import PrepareSemanticsNode
from app.agents.prompt_generation.visual_semantic_resolver.nodes import ResolveVisualSemanticsNode
from app.agents.prompt_generation.visual_semantic_resolver.nodes import ValidateVisualResultNode
VISUAL_SEMANTIC_RESOLVER_AGENT_NAME = "visual_semantic_resolver"

from app.agents.registry import agent_registry


class VisualSemanticResolverGraph:
    """Build the visual_semantic_resolver graph with native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(VisualSemanticResolverState)
        workflow.add_node("prepare_context", PrepareContextNode())
        workflow.add_node("prepare_semantics", PrepareSemanticsNode())
        workflow.add_node("resolve_visual_semantics", ResolveVisualSemanticsNode())
        workflow.add_node("validate_visual_result", ValidateVisualResultNode())
        workflow.add_edge("prepare_context", 'prepare_semantics')
        workflow.add_edge("prepare_semantics", 'resolve_visual_semantics')
        workflow.add_edge("resolve_visual_semantics", 'validate_visual_result')
        workflow.add_edge("validate_visual_result", END)
        workflow.set_entry_point("prepare_context")
        return workflow.compile()


def create_graph():
    """Create the visual_semantic_resolver agent graph."""

    return VisualSemanticResolverGraph().build_graph()


agent_registry.register(VISUAL_SEMANTIC_RESOLVER_AGENT_NAME, create_graph)

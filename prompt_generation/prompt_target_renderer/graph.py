"""Native LangGraph graph for the prompt_target_renderer agent."""

from langgraph.graph import END, StateGraph

from app.agents.prompt_generation.prompt_target_renderer.state import PromptTargetRendererState
from app.agents.prompt_generation.prompt_target_renderer.nodes import PrepareContextNode
from app.agents.prompt_generation.prompt_target_renderer.nodes import ValidateRenderInputNode
from app.agents.prompt_generation.prompt_target_renderer.nodes import RenderPromptNode
from app.agents.prompt_generation.prompt_target_renderer.nodes import ValidateRenderResultNode
PROMPT_TARGET_RENDERER_AGENT_NAME = "prompt_target_renderer"

from app.agents.registry import agent_registry


class PromptTargetRendererGraph:
    """Build the prompt_target_renderer graph with native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(PromptTargetRendererState)
        workflow.add_node("prepare_context", PrepareContextNode())
        workflow.add_node("validate_render_input", ValidateRenderInputNode())
        workflow.add_node("render_prompt", RenderPromptNode())
        workflow.add_node("validate_render_result", ValidateRenderResultNode())
        workflow.add_edge("prepare_context", 'validate_render_input')
        workflow.add_edge("validate_render_input", 'render_prompt')
        workflow.add_edge("render_prompt", 'validate_render_result')
        workflow.add_edge("validate_render_result", END)
        workflow.set_entry_point("prepare_context")
        return workflow.compile()


def create_graph():
    """Create the prompt_target_renderer agent graph."""

    return PromptTargetRendererGraph().build_graph()


agent_registry.register(PROMPT_TARGET_RENDERER_AGENT_NAME, create_graph)

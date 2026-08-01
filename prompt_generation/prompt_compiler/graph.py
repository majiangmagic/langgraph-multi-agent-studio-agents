"""Native LangGraph graph for the prompt_compiler agent."""

from langgraph.graph import END, StateGraph

from app.agents.prompt_generation.prompt_compiler.state import PromptCompilerState
from app.agents.prompt_generation.prompt_compiler.nodes import PrepareContextNode
from app.agents.prompt_generation.prompt_compiler.nodes import CollectTermsNode
from app.agents.prompt_generation.prompt_compiler.nodes import CompilePromptNode
from app.agents.prompt_generation.prompt_compiler.nodes import ValidatePromptIrNode
PROMPT_COMPILER_AGENT_NAME = "prompt_compiler"

from app.agents.registry import agent_registry


class PromptCompilerGraph:
    """Build the prompt_compiler graph with native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(PromptCompilerState)
        workflow.add_node("prepare_context", PrepareContextNode())
        workflow.add_node("collect_terms", CollectTermsNode())
        workflow.add_node("compile_prompt", CompilePromptNode())
        workflow.add_node("validate_prompt_ir", ValidatePromptIrNode())
        workflow.add_edge("prepare_context", 'collect_terms')
        workflow.add_edge("collect_terms", 'compile_prompt')
        workflow.add_edge("compile_prompt", 'validate_prompt_ir')
        workflow.add_edge("validate_prompt_ir", END)
        workflow.set_entry_point("prepare_context")
        return workflow.compile()


def create_graph():
    """Create the prompt_compiler agent graph."""

    return PromptCompilerGraph().build_graph()


agent_registry.register(PROMPT_COMPILER_AGENT_NAME, create_graph)

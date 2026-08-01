"""Native LangGraph graph for the prompt_consistency_validator agent."""

from langgraph.graph import END, StateGraph

from app.agents.prompt_generation.prompt_consistency_validator.state import PromptConsistencyValidatorState
from app.agents.prompt_generation.prompt_consistency_validator.nodes import PrepareContextNode
from app.agents.prompt_generation.prompt_consistency_validator.nodes import CollectInvariantsNode
from app.agents.prompt_generation.prompt_consistency_validator.nodes import ValidatePromptNode
from app.agents.prompt_generation.prompt_consistency_validator.nodes import FinalizeValidationNode
PROMPT_CONSISTENCY_VALIDATOR_AGENT_NAME = "prompt_consistency_validator"

from app.agents.registry import agent_registry


class PromptConsistencyValidatorGraph:
    """Build the prompt_consistency_validator graph with native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(PromptConsistencyValidatorState)
        workflow.add_node("prepare_context", PrepareContextNode())
        workflow.add_node("collect_invariants", CollectInvariantsNode())
        workflow.add_node("validate_prompt", ValidatePromptNode())
        workflow.add_node("finalize_validation", FinalizeValidationNode())
        workflow.add_edge("prepare_context", 'collect_invariants')
        workflow.add_edge("collect_invariants", 'validate_prompt')
        workflow.add_edge("validate_prompt", 'finalize_validation')
        workflow.add_edge("finalize_validation", END)
        workflow.set_entry_point("prepare_context")
        return workflow.compile()


def create_graph():
    """Create the prompt_consistency_validator agent graph."""

    return PromptConsistencyValidatorGraph().build_graph()


agent_registry.register(PROMPT_CONSISTENCY_VALIDATOR_AGENT_NAME, create_graph)

"""Native LangGraph graph for the prompt_semantic_repairer agent."""

from langgraph.graph import END, StateGraph

from app.agents.prompt_generation.prompt_semantic_repairer.state import PromptSemanticRepairerState
from app.agents.prompt_generation.prompt_semantic_repairer.nodes import PrepareContextNode
from app.agents.prompt_generation.prompt_semantic_repairer.nodes import CollectRepairScopeNode
from app.agents.prompt_generation.prompt_semantic_repairer.nodes import RepairSemanticsNode
from app.agents.prompt_generation.prompt_semantic_repairer.nodes import ValidateRepairNode
PROMPT_SEMANTIC_REPAIRER_AGENT_NAME = "prompt_semantic_repairer"

from app.agents.registry import agent_registry


class PromptSemanticRepairerGraph:
    """Build the prompt_semantic_repairer graph with native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(PromptSemanticRepairerState)
        workflow.add_node("prepare_context", PrepareContextNode())
        workflow.add_node("collect_repair_scope", CollectRepairScopeNode())
        workflow.add_node("repair_semantics", RepairSemanticsNode())
        workflow.add_node("validate_repair", ValidateRepairNode())
        workflow.add_edge("prepare_context", 'collect_repair_scope')
        workflow.add_edge("collect_repair_scope", 'repair_semantics')
        workflow.add_edge("repair_semantics", 'validate_repair')
        workflow.add_edge("validate_repair", END)
        workflow.set_entry_point("prepare_context")
        return workflow.compile()


def create_graph():
    """Create the prompt_semantic_repairer agent graph."""

    return PromptSemanticRepairerGraph().build_graph()


agent_registry.register(PROMPT_SEMANTIC_REPAIRER_AGENT_NAME, create_graph)

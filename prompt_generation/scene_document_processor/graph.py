"""Native LangGraph graph for the scene_document_processor agent."""

from langgraph.graph import END, StateGraph

from app.agents.prompt_generation.scene_document_processor.state import SceneDocumentProcessorState
from app.agents.prompt_generation.scene_document_processor.nodes import PrepareContextNode
from app.agents.prompt_generation.scene_document_processor.nodes import ValidatePatchNode
from app.agents.prompt_generation.scene_document_processor.nodes import ApplyPatchNode
from app.agents.prompt_generation.scene_document_processor.nodes import ValidateDocumentNode
from app.agents.prompt_generation.scene_document_processor.nodes import BuildAgentContextsNode
SCENE_DOCUMENT_PROCESSOR_AGENT_NAME = "scene_document_processor"

from app.agents.registry import agent_registry


class SceneDocumentProcessorGraph:
    """Build the scene_document_processor graph with native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(SceneDocumentProcessorState)
        workflow.add_node("prepare_context", PrepareContextNode())
        workflow.add_node("validate_patch", ValidatePatchNode())
        workflow.add_node("apply_patch", ApplyPatchNode())
        workflow.add_node("validate_document", ValidateDocumentNode())
        workflow.add_node("build_agent_contexts", BuildAgentContextsNode())
        workflow.add_edge("prepare_context", 'validate_patch')
        workflow.add_edge("validate_patch", 'apply_patch')
        workflow.add_edge("apply_patch", 'validate_document')
        workflow.add_edge("validate_document", 'build_agent_contexts')
        workflow.add_edge("build_agent_contexts", END)
        workflow.set_entry_point("prepare_context")
        return workflow.compile()


def create_graph():
    """Create the scene_document_processor agent graph."""

    return SceneDocumentProcessorGraph().build_graph()


agent_registry.register(SCENE_DOCUMENT_PROCESSOR_AGENT_NAME, create_graph)

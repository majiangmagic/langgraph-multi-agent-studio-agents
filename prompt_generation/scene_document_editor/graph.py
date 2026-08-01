"""Native LangGraph graph for the scene_document_editor agent."""

from langgraph.graph import END, StateGraph

from app.agents.prompt_generation.scene_document_editor.state import SceneDocumentEditorState
from app.agents.prompt_generation.scene_document_editor.nodes import PrepareContextNode
from app.agents.prompt_generation.scene_document_editor.nodes import PrepareRequestNode
from app.agents.prompt_generation.scene_document_editor.nodes import ProposePatchNode
from app.agents.prompt_generation.scene_document_editor.nodes import ValidatePatchNode
SCENE_DOCUMENT_EDITOR_AGENT_NAME = "scene_document_editor"

from app.agents.registry import agent_registry


class SceneDocumentEditorGraph:
    """Build the scene_document_editor graph with native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(SceneDocumentEditorState)
        workflow.add_node("prepare_context", PrepareContextNode())
        workflow.add_node("prepare_request", PrepareRequestNode())
        workflow.add_node("propose_patch", ProposePatchNode())
        workflow.add_node("validate_patch", ValidatePatchNode())
        workflow.add_edge("prepare_context", 'prepare_request')
        workflow.add_edge("prepare_request", 'propose_patch')
        workflow.add_edge("propose_patch", 'validate_patch')
        workflow.add_edge("validate_patch", END)
        workflow.set_entry_point("prepare_context")
        return workflow.compile()


def create_graph():
    """Create the scene_document_editor agent graph."""

    return SceneDocumentEditorGraph().build_graph()


agent_registry.register(SCENE_DOCUMENT_EDITOR_AGENT_NAME, create_graph)

"""Native LangGraph graph for the character_identity_resolver agent."""

from langgraph.graph import END, StateGraph

from app.agents.prompt_generation.character_identity_resolver.state import CharacterIdentityResolverState
from app.agents.prompt_generation.character_identity_resolver.nodes import PrepareContextNode
from app.agents.prompt_generation.character_identity_resolver.nodes import CollectIdentitiesNode
from app.agents.prompt_generation.character_identity_resolver.nodes import ResolveIdentitiesNode
from app.agents.prompt_generation.character_identity_resolver.nodes import ValidateIdentityResultNode
CHARACTER_IDENTITY_RESOLVER_AGENT_NAME = "character_identity_resolver"

from app.agents.registry import agent_registry


class CharacterIdentityResolverGraph:
    """Build the character_identity_resolver graph with native LangGraph operations."""

    def build_graph(self):
        workflow = StateGraph(CharacterIdentityResolverState)
        workflow.add_node("prepare_context", PrepareContextNode())
        workflow.add_node("collect_identities", CollectIdentitiesNode())
        workflow.add_node("resolve_identities", ResolveIdentitiesNode())
        workflow.add_node("validate_identity_result", ValidateIdentityResultNode())
        workflow.add_edge("prepare_context", 'collect_identities')
        workflow.add_edge("collect_identities", 'resolve_identities')
        workflow.add_edge("resolve_identities", 'validate_identity_result')
        workflow.add_edge("validate_identity_result", END)
        workflow.set_entry_point("prepare_context")
        return workflow.compile()


def create_graph():
    """Create the character_identity_resolver agent graph."""

    return CharacterIdentityResolverGraph().build_graph()


agent_registry.register(CHARACTER_IDENTITY_RESOLVER_AGENT_NAME, create_graph)

"""Constants and node factories for the Harness checker agent."""

from app.agents.harness.harness_checker.nodes import (
    FunctionalityCheckerNode,
    GitCheckpointCreatorNode,
    DocumentCheckerNode,
)

HARNESS_CHECKER_AGENT_NAME = "harness_checker"
HARNESS_CHECKER_ENTRYPOINT = "functionality_checker"


def create_document_checker_node() -> DocumentCheckerNode:
    """Create the node that runs all Harness check.py validations."""

    return DocumentCheckerNode()


def create_functionality_checker_node() -> FunctionalityCheckerNode:
    """Create the completed-feature checker."""

    return FunctionalityCheckerNode()


def create_git_checkpoint_creator_node() -> GitCheckpointCreatorNode:
    """Create the local Git checkpoint node."""

    return GitCheckpointCreatorNode()

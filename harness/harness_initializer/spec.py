"""Constants and node factory for the harness initializer agent."""

from app.agents.harness.harness_initializer.nodes import EnvironmentCheckerNode, GitRepoCreatorNode, MarkdownCreatorNode

HARNESS_INITIALIZER_AGENT_NAME = "harness_initializer"
HARNESS_INITIALIZER_ENTRYPOINT = "environment_checker"
HARNESS_TEMPLATE_DIRECTORY = "templates/harness"
REQUIRED_DOCUMENTS = [
    "AGENT.md",
    "PLANER.md",
    "RUNTIME.md",
    "CHECKER.md",
    "ARCHITECTURE.md",
    "PROGRESS.md",
    "DECISIONS.md",
    "FEATURES.md",
]
DEFAULT_DOCUMENTS = list(REQUIRED_DOCUMENTS)


def create_environment_checker_node() -> EnvironmentCheckerNode:
    """Create the environment checker node."""

    return EnvironmentCheckerNode()


def create_markdown_creator_node() -> MarkdownCreatorNode:
    """Create the markdown creator node."""

    return MarkdownCreatorNode()


def create_git_repo_creator_node() -> GitRepoCreatorNode:
    """Create the local git repository creator node."""

    return GitRepoCreatorNode()

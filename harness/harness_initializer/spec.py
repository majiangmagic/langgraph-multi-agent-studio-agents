"""Constants and node factory for the harness initializer agent."""

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

SCRIPT_CREATED_DOCUMENTS = [
    ("ARCHITECTURE.md", "Architecture_Editor", "architecture.example.json"),
    ("PROGRESS.md", "Progress_Editor", "progress.example.json"),
    ("DECISIONS.md", "Decisions_Editor", "decisions.example.json"),
    ("FEATURES.md", "Features_Editor", "features.example.json"),
]


def create_environment_checker_node():
    """Create the environment checker node."""

    from app.agents.harness.harness_initializer.nodes import EnvironmentCheckerNode

    return EnvironmentCheckerNode()


def create_markdown_creator_node():
    """Create the markdown creator node."""

    from app.agents.harness.harness_initializer.nodes import MarkdownCreatorNode

    return MarkdownCreatorNode()


def create_git_repo_creator_node():
    """Create the local git repository creator node."""

    from app.agents.harness.harness_initializer.nodes import GitRepoCreatorNode

    return GitRepoCreatorNode()

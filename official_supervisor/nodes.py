"""Node handlers for the official supervisor Agent example."""

from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from app.agents.official_supervisor.state import SupervisorState


class SupervisorExampleOnlyError(RuntimeError):
    """Raised when the non-runnable supervisor example is invoked."""


class SupervisorExampleNode:
    """Fail-fast node retained only to demonstrate an Agent graph skeleton."""

    def __call__(
        self,
        state: SupervisorState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        raise SupervisorExampleOnlyError(
            "official_supervisor is an example Agent skeleton and has no standalone "
            "runtime. Use create_workflow_supervisor_graph inside a real workflow."
        )

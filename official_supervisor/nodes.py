"""Node handlers for the official supervisor agent."""

from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from app.agents.official_supervisor.official_runtime import OfficialSupervisorRuntime
from app.agents.official_supervisor.state import SupervisorState


class OfficialSupervisorNode:
    """Object-oriented node adapter for the official supervisor runtime."""

    def __init__(self, runtime: OfficialSupervisorRuntime | None = None) -> None:
        self.runtime = runtime or OfficialSupervisorRuntime()

    def __call__(
        self,
        state: SupervisorState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        """Run the supervisor runtime for the current agent state."""

        runtime = self.runtime.with_state_config(state)
        return runtime.invoke(state, config=config)

"""Node handlers for the official supervisor agent."""

from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from app.agents.official_supervisor.official_runtime import OfficialSupervisorRuntime
from app.agents.official_supervisor.state import SupervisorState


def official_supervisor_node(
    state: SupervisorState,
    config: RunnableConfig | None = None,
) -> Dict[str, Any]:
    """Run the official supervisor runtime for the current agent state."""

    runtime = OfficialSupervisorRuntime().with_state_config(state)
    return runtime.invoke(state, config=config)

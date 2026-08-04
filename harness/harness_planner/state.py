"""State schema for the harness planner agent."""

from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage


class HarnessPlannerState(TypedDict, total=False):
    """Runtime state for planning updates in an existing project."""

    agent_id: str
    agent_name: str
    description: Optional[str]
    system_prompt: Optional[str]
    model: Optional[str]
    temperature: float
    tools: List[Dict[str, Any]]
    messages: List[BaseMessage]
    user_input: Optional[str]
    workflow_inputs: Dict[str, Any]
    request_context: Dict[str, Any]
    target_directory: Optional[str]
    harness_template_directory: Optional[str]
    status: Optional[str]
    results: Optional[Dict[str, Any]]
    error: Optional[str]

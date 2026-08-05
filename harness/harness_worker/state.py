"""State schema for the Harness worker agent."""

from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage


class HarnessWorkerState(TypedDict, total=False):
    """Runtime state for executing the current work in PROGRESS.md."""

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
    status: Optional[str]
    results: Optional[Dict[str, Any]]
    error: Optional[str]

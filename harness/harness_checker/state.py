"""State schema for the Harness checker agent."""

from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage


class HarnessCheckerState(TypedDict, total=False):
    """Runtime state for validating and archiving completed Harness work."""

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
    markdown_issues: List[Dict[str, str]]
    validation: Dict[str, Any]
    remake_count: int
    status: Optional[str]
    results: Optional[Dict[str, Any]]
    error: Optional[str]

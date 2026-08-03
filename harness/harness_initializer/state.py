"""State schema for the harness initializer agent."""

from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage


class HarnessInitializerState(TypedDict):
    """Runtime state for bootstrapping a fresh project."""

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
    should_initialize: bool
    skip_reason: Optional[str]
    created_files: List[str]
    created_directories: List[str]
    git_initialized: bool
    git_commit: Optional[str]
    harness_copied: bool
    status: Optional[str]
    results: Optional[Dict[str, Any]]
    error: Optional[str]

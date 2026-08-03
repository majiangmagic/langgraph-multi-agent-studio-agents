"""Node handlers for the harness initializer agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from app.agents.harness.harness_initializer.spec import HARNESS_TEMPLATE_DIRECTORY, REQUIRED_DOCUMENTS
from app.agents.harness.harness_initializer.state import HarnessInitializerState


class EnvironmentCheckerNode:
    """Check whether the target directory is a fresh project."""

    def __call__(
        self,
        state: HarnessInitializerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        target_directory = resolve_target_directory(state)
        template_directory = resolve_template_directory(state)
        fresh_environment = is_fresh_environment(target_directory)
        if not fresh_environment:
            skip_reason = (
                f"Harness initializer skipped because the required documents already exist in {target_directory}"
            )
            return {
                "target_directory": str(target_directory),
                "harness_template_directory": str(template_directory),
                "should_initialize": False,
                "skip_reason": skip_reason,
                "status": "complete",
                "results": {
                    "fresh_environment": False,
                    "target_directory": str(target_directory),
                    "skip_reason": skip_reason,
                },
                "created_files": state.get("created_files", []),
                "created_directories": state.get("created_directories", []),
                "git_initialized": False,
                "git_commit": None,
                "harness_copied": False,
            }
        return {
            "target_directory": str(target_directory),
            "harness_template_directory": str(template_directory),
            "should_initialize": True,
            "skip_reason": None,
            "status": "working",
            "results": {
                "fresh_environment": True,
                "target_directory": str(target_directory),
            },
            "created_files": [],
            "created_directories": [],
            "git_initialized": False,
            "git_commit": None,
            "harness_copied": False,
        }


class MarkdownCreatorNode:
    """Placeholder initialization step for future Harness document creation."""

    def __call__(
        self,
        state: HarnessInitializerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        if not state.get("should_initialize"):
            return {}

        return {
            "status": "working",
            "results": {
                **(state.get("results") or {}),
                "initialization_phase": "markdown_creator_placeholder",
            },
        }


class GitRepoCreatorNode:
    """Placeholder initialization step for future local git setup."""

    def __call__(
        self,
        state: HarnessInitializerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        if not state.get("should_initialize"):
            return {}

        return {
            "status": "complete",
            "results": {
                **(state.get("results") or {}),
                "initialization_phase": "git_repo_creator_placeholder",
            },
        }


def resolve_target_directory(state: HarnessInitializerState) -> Path:
    """Resolve the project directory to bootstrap."""

    workflow_inputs = state.get("workflow_inputs") or {}
    raw_value = (
        workflow_inputs.get("target_directory")
        or workflow_inputs.get("project_directory")
        or state.get("user_input")
        or state.get("request_context", {}).get("target_directory")
    )
    if raw_value is None or not str(raw_value).strip():
        raise ValueError("harness_initializer requires a target directory")
    return Path(str(raw_value)).expanduser().resolve()


def resolve_template_directory(state: HarnessInitializerState) -> Path:
    """Resolve the bundled Harness template directory."""

    workflow_inputs = state.get("workflow_inputs") or {}
    raw_value = (
        workflow_inputs.get("harness_template_directory")
        or workflow_inputs.get("template_directory")
        or state.get("harness_template_directory")
    )
    if raw_value:
        return Path(str(raw_value)).expanduser().resolve()
    return Path(__file__).resolve().parent / HARNESS_TEMPLATE_DIRECTORY


def is_fresh_environment(target_directory: Path) -> bool:
    """Treat the project as fresh until every required Harness document exists."""

    if not target_directory.exists():
        return True
    if not target_directory.is_dir():
        raise ValueError(f"Target path is not a directory: {target_directory}")

    for filename in REQUIRED_DOCUMENTS:
        if not (target_directory / filename).exists():
            return True
    return False

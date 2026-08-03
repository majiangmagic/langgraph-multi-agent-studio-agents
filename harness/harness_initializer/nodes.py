"""Node handlers for the harness initializer agent."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from app.agents.harness.harness_initializer.spec import DEFAULT_DOCUMENTS, HARNESS_TEMPLATE_DIRECTORY
from app.agents.harness.harness_initializer.state import HarnessInitializerState

IGNORED_DIRECTORY_NAMES = {".DS_Store", "Thumbs.db"}


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
            skip_reason = f"?????????????? Harness ????{target_directory}"
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
    """Create the empty Harness markdown documents and copy the template folder."""

    def __call__(
        self,
        state: HarnessInitializerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        if not state.get("should_initialize"):
            return {}

        target_directory = resolve_target_directory(state)
        template_directory = resolve_template_directory(state)
        target_directory.mkdir(parents=True, exist_ok=True)

        created_files: List[str] = list(state.get("created_files") or [])
        created_directories: List[str] = list(state.get("created_directories") or [])

        for filename in DEFAULT_DOCUMENTS:
            file_path = target_directory / filename
            file_path.write_text("", encoding="utf-8")
            created_files.append(str(file_path))

        harness_target = target_directory / "harness"
        harness_target.mkdir(parents=True, exist_ok=True)
        created_directories.append(str(harness_target))
        copy_harness_template(template_directory, harness_target)

        return {
            "created_files": dedupe_paths(created_files),
            "created_directories": dedupe_paths(created_directories),
            "harness_copied": True,
            "results": {
                **(state.get("results") or {}),
                "documents_created": DEFAULT_DOCUMENTS,
                "harness_directory": str(harness_target),
            },
            "status": "working",
        }


class GitRepoCreatorNode:
    """Initialize a local git repository without creating any remote."""

    def __call__(
        self,
        state: HarnessInitializerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        if not state.get("should_initialize"):
            return {}

        target_directory = resolve_target_directory(state)
        target_directory.mkdir(parents=True, exist_ok=True)

        git_init_result = run_git_command(target_directory, ["init", "-b", "main"])
        if git_init_result.returncode != 0:
            git_init_result = run_git_command(target_directory, ["init"])
            if git_init_result.returncode != 0:
                raise RuntimeError(format_command_failure("git init", git_init_result))

        run_git_command(target_directory, ["add", "-A"])
        commit_result = run_git_command(
            target_directory,
            ["commit", "-m", "chore: bootstrap harness"],
        )

        git_commit = None
        if commit_result.returncode == 0:
            head_result = run_git_command(target_directory, ["rev-parse", "HEAD"])
            if head_result.returncode == 0:
                git_commit = head_result.stdout.strip()

        return {
            "git_initialized": True,
            "git_commit": git_commit,
            "status": "complete",
            "results": {
                **(state.get("results") or {}),
                "git_initialized": True,
                "git_commit": git_commit,
                "git_init_output": (git_init_result.stdout or git_init_result.stderr).strip(),
                "git_commit_output": (commit_result.stdout or commit_result.stderr).strip(),
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
    """Treat an empty directory or missing path as a fresh environment."""

    if not target_directory.exists():
        return True
    if not target_directory.is_dir():
        raise ValueError(f"Target path is not a directory: {target_directory}")
    for child in target_directory.iterdir():
        if child.name in IGNORED_DIRECTORY_NAMES:
            continue
        return False
    return True


def copy_harness_template(source_directory: Path, target_directory: Path) -> None:
    """Copy the bundled Harness support files into the new project."""

    if not source_directory.is_dir():
        raise ValueError(f"Harness template directory not found: {source_directory}")
    for item in source_directory.iterdir():
        if item.name == "__pycache__":
            continue
        destination = target_directory / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def run_git_command(target_directory: Path, arguments: List[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command inside the target directory."""

    return subprocess.run(
        ["git", *arguments],
        cwd=target_directory,
        capture_output=True,
        text=True,
        check=False,
    )


def format_command_failure(command: str, result: subprocess.CompletedProcess[str]) -> str:
    """Format a git command failure for debugging."""

    output = (result.stdout or "") + (result.stderr or "")
    return f"{command} failed with exit code {result.returncode}: {output.strip()}"


def dedupe_paths(paths: List[str]) -> List[str]:
    """Preserve order while removing duplicate file paths."""

    seen = set()
    deduped: List[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped

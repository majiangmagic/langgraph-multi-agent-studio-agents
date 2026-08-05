"""Node handlers for the harness initializer agent."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from app.agents.harness.harness_initializer.spec import SCRIPT_CREATED_DOCUMENTS, HARNESS_TEMPLATE_DIRECTORY, REQUIRED_DOCUMENTS
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
                "input_sufficient": True,
                "clarification_request": None,
                "clarification_answer": None,
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
        clarification_answer = state.get("clarification_answer")
        source_text = "\n".join(
            value
            for value in (state.get("user_input"), clarification_answer)
            if value and str(value).strip()
        )
        input_sufficient, missing_information = assess_project_context(
            source_text, state.get("workflow_inputs") or {}
        )

        return {
            "target_directory": str(target_directory),
            "harness_template_directory": str(template_directory),
            "should_initialize": True,
            "input_sufficient": input_sufficient,
            "clarification_answer": clarification_answer,
            "clarification_request": (
                {
                    "question": build_context_question(missing_information),
                    "missing_information": missing_information,
                }
                if not input_sufficient
                else None
            ),
            "skip_reason": (
                "\u9996\u6b21\u521d\u59cb\u5316\u5f85\u8865\u5145\u9879\u76ee\u57fa\u7840\u4fe1\u606f\u3002"
                if not input_sufficient
                else None
            ),
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
    """Create Harness documents with scripts and copied markdown examples."""

    def __call__(
        self,
        state: HarnessInitializerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        if not state.get("should_initialize"):
            return {}

        target_directory = resolve_target_directory(state)
        template_directory = resolve_template_directory(state)
        harness_directory = target_directory / "harness"
        md_example_directory = template_directory / "md_example"

        target_directory.mkdir(parents=True, exist_ok=True)
        copy_harness_support_files(template_directory, harness_directory)
        created_files = create_markdown_with_harness_context(harness_directory, target_directory)
        created_files.extend(copy_markdown_examples(md_example_directory, target_directory))

        return {
            "created_files": dedupe_paths(created_files),
            "created_directories": [str(harness_directory)],
            "harness_copied": True,
            "status": "working",
            "results": {
                **(state.get("results") or {}),
                "script_created_documents": SCRIPT_CREATED_DOCUMENTS,
                "copied_markdown_example_directory": str(md_example_directory),
                "harness_directory": str(harness_directory),
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

        clarification_answer = state.get("clarification_answer")
        if not state.get("input_sufficient") and not clarification_answer:
            clarification_answer = str(
                interrupt({
                    "kind": "workflow.clarification",
                    "question": build_context_question(
                        (state.get("clarification_request") or {}).get(
                            "missing_information", []
                        )
                    ),
                    "options": [],
                    "context": "\u6587\u4ef6\u5df2\u521b\u5efa\uff0c\u8bf7\u8865\u5145\u9879\u76ee\u80cc\u666f\u3001\u6280\u672f\u6808\u548c\u5e38\u7528\u547d\u4ee4\uff0c\u4e0b\u4e00\u8f6e\u5c06\u7531 harness_planner \u5199\u5165\u6587\u6863\u3002",
                })
                or ""
            ).strip()

        return {
            "clarification_answer": clarification_answer,
            "status": "complete",
            "results": {
                **(state.get("results") or {}),
                "initialization_phase": "git_repo_creator_placeholder",
                "context_collection": "deferred_to_harness_planner"
                if not state.get("input_sufficient")
                else "complete",
            },
        }



def assess_project_context(text: str, workflow_inputs: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Check whether a fresh project request contains minimum bootstrap context."""

    context = workflow_inputs.get("project_context")
    if isinstance(context, dict):
        combined = "\n".join(str(value) for value in context.values() if value)
    else:
        combined = ""
    content = f"{text}\n{combined}".lower()
    categories = {
        "\u9879\u76ee\u80cc\u666f": (
            "\u9879\u76ee", "\u7528\u9014", "\u76ee\u6807", "\u80cc\u666f",
            "\u5f00\u53d1", "\u5b9e\u73b0", "project", "purpose", "goal",
        ),
        "\u6280\u672f\u6808": (
            "python", "javascript", "typescript", "java", "go", "rust",
            "react", "vue", "fastapi", "\u6280\u672f\u6808", "\u6846\u67b6",
            "\u6570\u636e\u5e93", "stack", "framework",
        ),
        "\u5e38\u7528\u6307\u4ee4": (
            "\u547d\u4ee4", "\u6307\u4ee4", "\u542f\u52a8", "\u8fd0\u884c", "\u6d4b\u8bd5",
            "\u5b89\u88c5", "\u90e8\u7f72", "npm", "pnpm", "pip", "uv", "pytest",
            "docker", "command", "run", "test",
        ),
    }
    missing = [
        name for name, keywords in categories.items()
        if not any(keyword in content for keyword in keywords)
    ]
    return not missing, missing


def build_context_question(missing_information: List[str]) -> str:
    """Build a direct clarification request for the missing bootstrap context."""

    missing_text = "\u3001".join(missing_information) or "\u9879\u76ee\u57fa\u7840\u4fe1\u606f"
    return (
        f"\u8fd9\u662f\u4e00\u4e2a\u65b0\u9879\u76ee\uff0c\u521d\u59cb\u5316\u524d\u8fd8\u7f3a\u5c11\uff1a{missing_text}\u3002"
        "\u8bf7\u8865\u5145\u9879\u76ee\u80cc\u666f\u3001\u6280\u672f\u6808\u548c\u5e38\u7528\u542f\u52a8\u6216\u6d4b\u8bd5\u547d\u4ee4\u4e2d\u7f3a\u5c11\u7684\u5185\u5bb9\u3002"
    )


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


def copy_harness_support_files(source_directory: Path, target_directory: Path) -> None:
    """Copy bundled Harness scripts and examples into the target project."""

    if not source_directory.is_dir():
        raise ValueError(f"Harness template directory not found: {source_directory}")
    target_directory.mkdir(parents=True, exist_ok=True)
    for item in source_directory.iterdir():
        if item.name == "__pycache__" or item.name == "md_example":
            continue
        destination = target_directory / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                destination,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(item, destination)


def create_markdown_with_harness_context(harness_directory: Path, target_directory: Path) -> List[str]:
    """Use harness_context.py and JSON examples to create supported markdown files."""

    script_path = harness_directory / "harness_context.py"
    json_example_directory = harness_directory / "json_example"
    if not script_path.is_file():
        raise ValueError(f"Harness context script not found: {script_path}")

    created_files: List[str] = []
    for document_name, operation_name, json_filename in SCRIPT_CREATED_DOCUMENTS:
        input_path = json_example_directory / json_filename
        output_path = target_directory / document_name
        if not input_path.is_file():
            raise ValueError(f"Harness JSON example not found: {input_path}")
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--operation",
                operation_name,
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
            cwd=target_directory,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            raise RuntimeError(f"{operation_name} failed with exit code {result.returncode}: {output}")
        created_files.append(str(output_path))
    return created_files


def copy_markdown_examples(source_directory: Path, target_directory: Path) -> List[str]:
    """Copy markdown files that cannot be generated by harness_context.py yet."""

    if not source_directory.exists():
        return []
    if not source_directory.is_dir():
        raise ValueError(f"Harness markdown example path is not a directory: {source_directory}")

    created_files: List[str] = []
    for item in source_directory.iterdir():
        if item.name == "__pycache__":
            continue
        destination = target_directory / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                destination,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        elif item.suffix.lower() == ".md":
            shutil.copy2(item, destination)
            created_files.append(str(destination))
    return created_files


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

"""Node handler for the Harness worker agent."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from app.agents.harness.harness_initializer.nodes import resolve_target_directory
from app.agents.harness.harness_worker.state import HarnessWorkerState


class HarnessWorkerNode:
    """Use Codex CLI to execute the current work described in PROGRESS.md."""

    def __call__(
        self,
        state: HarnessWorkerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        target_directory = resolve_target_directory(state)
        progress_path = target_directory / "PROGRESS.md"
        runtime_path = target_directory / "RUNTIME.md"
        if not progress_path.is_file():
            raise FileNotFoundError(f"PROGRESS.md does not exist: {progress_path}")
        if not runtime_path.is_file():
            raise FileNotFoundError(f"RUNTIME.md does not exist: {runtime_path}")

        progress_text = read_required_document(progress_path)
        runtime_text = read_required_document(runtime_path)
        if not progress_text.strip():
            raise ValueError("PROGRESS.md is empty; harness_worker has no work to execute")
        if not runtime_text.strip():
            raise ValueError("RUNTIME.md is empty; harness_worker cannot start work")

        verify_planner_updated_progress(state, progress_path)
        result = run_codex_cli(target_directory)
        execution = {
            "exit_code": result.returncode,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
        }
        if result.returncode != 0:
            return {
                "status": "error",
                "error": summarize_codex_failure(result),
                "results": {
                    "target_directory": str(target_directory),
                    "progress_path": str(progress_path),
                    "execution": execution,
                },
            }

        return {
            "status": "complete",
            "error": None,
            "results": {
                "target_directory": str(target_directory),
                "progress_path": str(progress_path),
                "runtime_path": str(runtime_path),
                "execution": execution,
                "codex_status": "passed",
            },
        }


def read_required_document(path: Path) -> str:
    """Read a required Harness document as strict UTF-8."""

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name} is not valid UTF-8: {path}") from exc


def verify_planner_updated_progress(state: HarnessWorkerState, progress_path: Path) -> None:
    """Refuse to start work unless the planner changed the current PROGRESS.md."""

    planner_results = state.get("planner_results") or {}
    before_snapshots = planner_results.get("before_snapshots") or {}
    after_snapshots = planner_results.get("after_snapshots") or {}
    before_progress = before_snapshots.get("PROGRESS.md") or {}
    after_progress = after_snapshots.get("PROGRESS.md") or {}
    before_hash = before_progress.get("sha256")
    after_hash = after_progress.get("sha256")

    if not before_hash or not after_hash or before_hash == after_hash:
        raise ValueError(
            "harness_planner did not update PROGRESS.md; ask the planner to update "
            "PROGRESS.md before starting harness_worker"
        )

    current_hash = hashlib.sha256(progress_path.read_bytes()).hexdigest()
    if current_hash != after_hash:
        raise ValueError(
            "PROGRESS.md changed after harness_planner finished; ask the planner to "
            "review and update PROGRESS.md again before starting harness_worker"
        )


def build_worker_prompt() -> str:
    """Build the Codex instruction for executing the current planned work."""

    return "\n".join(
        [
            "You are harness_worker.",
            "Read RUNTIME.md before making any changes. This is mandatory.",
            "Follow every applicable development and verification rule in RUNTIME.md.",
            "Then read PROGRESS.md and execute the current unfinished work described there.",
            "Read AGENT.md when project-specific context or commands are needed.",
            "Implement the work in the project; do not merely describe a solution.",
            "Keep the implementation focused on the current PROGRESS.md task.",
            "Run the relevant verification commands before finishing.",
            "Update PROGRESS.md with the actual execution result and remaining work.",
            "Do not invent additional tasks outside the current plan.",
        ]
    )


def run_codex_cli(target_directory: Path) -> subprocess.CompletedProcess[str]:
    """Run Codex CLI in the target project directory."""

    return subprocess.run(
        [
            "codex",
            "exec",
            "--cd",
            str(target_directory),
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            build_worker_prompt(),
        ],
        cwd=target_directory,
        capture_output=True,
        text=True,
        check=False,
    )


def summarize_codex_failure(result: subprocess.CompletedProcess[str]) -> str:
    """Create a concise worker failure message."""

    output = (result.stderr or result.stdout or "").strip()
    if output:
        return f"Harness worker Codex execution failed: {output[:1600]}"
    return f"Harness worker Codex execution failed with exit code {result.returncode}"

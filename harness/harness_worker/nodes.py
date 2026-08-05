"""Node handler for the Harness worker agent."""

from __future__ import annotations

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
        if not progress_path.is_file():
            raise FileNotFoundError(f"PROGRESS.md does not exist: {progress_path}")

        progress_text = read_utf8(progress_path)
        if not progress_text.strip():
            raise ValueError("PROGRESS.md is empty; harness_worker has no work to execute")

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
                "execution": execution,
                "codex_status": "passed",
            },
        }


def read_utf8(path: Path) -> str:
    """Read required worker instructions as strict UTF-8."""

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"PROGRESS.md is not valid UTF-8: {path}") from exc


def build_worker_prompt() -> str:
    """Build the Codex instruction for executing the current planned work."""

    return "\n".join(
        [
            "You are harness_worker.",
            "Read PROGRESS.md first and execute the current unfinished work described there.",
            "Use AGENT.md and RUNTIME.md as project instructions when they are relevant.",
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

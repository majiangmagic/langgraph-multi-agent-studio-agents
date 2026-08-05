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
    """Use Codex CLI to execute and record the current work."""

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
        if not read_required_document(progress_path).strip():
            raise ValueError("PROGRESS.md is empty; harness_worker has no work to execute")
        if not read_required_document(runtime_path).strip():
            raise ValueError("RUNTIME.md is empty; harness_worker cannot start work")

        attempts = []
        prompt = build_worker_prompt()
        for attempt_number in range(1, MAX_CODEX_ATTEMPTS + 1):
            before_hash = hash_file(progress_path)
            result = run_codex_cli(target_directory, prompt)
            after_hash = hash_file(progress_path)
            execution = {
                "attempt": attempt_number,
                "exit_code": result.returncode,
                "progress_before_sha256": before_hash,
                "progress_after_sha256": after_hash,
                "progress_changed": before_hash != after_hash,
                "stdout": result.stdout[-12000:],
                "stderr": result.stderr[-12000:],
            }
            attempts.append(execution)
            if result.returncode == 0 and before_hash != after_hash:
                return {
                    "status": "complete",
                    "error": None,
                    "results": {
                        "target_directory": str(target_directory),
                        "progress_path": str(progress_path),
                        "runtime_path": str(runtime_path),
                        "attempts": attempts,
                        "codex_status": "passed",
                    },
                }
            prompt = build_worker_retry_prompt(result.returncode, before_hash == after_hash)

        return {
            "status": "error",
            "error": "harness_worker Codex CLI did not update PROGRESS.md after two attempts; it may have forgotten to update the document.",
            "results": {
                "target_directory": str(target_directory),
                "progress_path": str(progress_path),
                "runtime_path": str(runtime_path),
                "attempts": attempts,
                "codex_status": "failed",
            },
        }


def read_required_document(path: Path) -> str:
    """Read a required Harness document as strict UTF-8."""

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{path.name} is not valid UTF-8: {path}") from exc


def hash_file(path: Path) -> str:
    """Return the SHA-256 hash of a document."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


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


MAX_CODEX_ATTEMPTS = 2


def build_worker_retry_prompt(exit_code: int, progress_unchanged: bool) -> str:
    """Ask Codex to finish the work and update PROGRESS.md."""

    if progress_unchanged:
        reason = "PROGRESS.md did not change; did you forget to update the document?"
    else:
        reason = f"The previous Codex run failed with exit code {exit_code}."
    return "\n".join(
        [
            build_worker_prompt(),
            reason,
            "Review the actual work you performed, then update PROGRESS.md with the completed work, verification result, and remaining work before finishing.",
        ]
    )


def run_codex_cli(target_directory: Path, prompt: str) -> subprocess.CompletedProcess[str]:
    """Run Codex CLI in the target project directory."""

    return subprocess.run(
        [
            "codex",
            "exec",
            "--cd",
            str(target_directory),
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            prompt,
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

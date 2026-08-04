"""Node handlers for the harness planner agent."""

from __future__ import annotations

import hashlib
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from app.agents.harness.harness_initializer.nodes import resolve_target_directory, resolve_template_directory
from app.agents.harness.harness_planner.state import HarnessPlannerState


logger = logging.getLogger(__name__)
PLANNED_DOCUMENTS = ("PROGRESS.md", "FEATURES.md", "DECISIONS.md")
MAX_CODEX_ATTEMPTS = 2
GARBLED_PATTERNS = ("\ufffd", "???")


@dataclass(frozen=True)
class DocumentSnapshot:
    """Pre- and post-run document snapshot."""

    path: Path
    exists: bool
    sha256: str | None
    size: int | None
    has_garble: bool


class HarnessPlannerNode:
    """Plan the next maintenance pass for an existing project."""

    def __call__(
        self,
        state: HarnessPlannerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        target_directory = resolve_target_directory(state)
        template_directory = resolve_template_directory(state)
        if not target_directory.exists():
            raise FileNotFoundError(f"Target directory does not exist: {target_directory}")
        if not target_directory.is_dir():
            raise NotADirectoryError(f"Target path is not a directory: {target_directory}")

        before_snapshots = collect_document_snapshots(target_directory)
        attempts: List[Dict[str, Any]] = []
        last_stderr = ""

        prompt = build_codex_prompt(target_directory, template_directory, before_snapshots)
        for attempt_index in range(1, MAX_CODEX_ATTEMPTS + 1):
            result = run_codex_cli(target_directory, prompt)
            after_snapshots = collect_document_snapshots(target_directory)
            missing_updates = find_missing_updates(before_snapshots, after_snapshots)
            garbled_documents = find_garbled_documents(after_snapshots)

            attempts.append(
                {
                    "attempt": attempt_index,
                    "exit_code": result.returncode,
                    "missing_updates": missing_updates,
                    "garbled_documents": garbled_documents,
                    "stdout": result.stdout[-8000:],
                    "stderr": result.stderr[-8000:],
                }
            )
            last_stderr = result.stderr

            if result.returncode == 0 and not missing_updates and not garbled_documents:
                return {
                    "status": "complete",
                    "results": {
                        "target_directory": str(target_directory),
                        "template_directory": str(template_directory),
                        "before_snapshots": snapshots_to_json(before_snapshots),
                        "after_snapshots": snapshots_to_json(after_snapshots),
                        "attempts": attempts,
                        "codex_status": "passed",
                    },
                    "error": None,
                }

            prompt = build_retry_prompt(missing_updates, garbled_documents)

        final_after_snapshots = collect_document_snapshots(target_directory)
        final_missing_updates = find_missing_updates(before_snapshots, final_after_snapshots)
        final_garbled_documents = find_garbled_documents(final_after_snapshots)
        logger.warning(
            "Harness planner ended with unresolved documents: missing=%s garbled=%s",
            final_missing_updates,
            final_garbled_documents,
        )
        return {
            "status": "error",
            "error": summarize_failures(final_missing_updates, final_garbled_documents, last_stderr),
            "results": {
                "target_directory": str(target_directory),
                "template_directory": str(template_directory),
                "before_snapshots": snapshots_to_json(before_snapshots),
                "after_snapshots": snapshots_to_json(final_after_snapshots),
                "attempts": attempts,
                "codex_status": "failed",
            },
        }


def build_codex_prompt(target_directory: Path, template_directory: Path, snapshots: Dict[str, DocumentSnapshot]) -> str:
    """Build the initial Codex prompt for the planner stage."""

    planned_status = [
        f"- {name}: {'exists' if snapshot.exists else 'missing'}"
        for name, snapshot in snapshots.items()
    ]
    return "\n".join(
        [
            "You are harness_planner.",
            f"Work inside: {target_directory}",
            f"Harness templates: {template_directory}",
            "Read PLANER.md in the current project before making any changes.",
            "Update PROGRESS.md, FEATURES.md, and DECISIONS.md when needed.",
            "Keep all files in clean UTF-8 and avoid garbled text.",
            "If a tracked file truly does not need a change, explain why in the final response.",
            "Tracked document status before the run:",
            *planned_status,
            "Focus only on the three tracked docs unless the plan explicitly requires something else.",
        ]
    )


def build_retry_prompt(missing_updates: List[str], garbled_documents: List[str]) -> str:
    """Build a stricter follow-up prompt after an incomplete Codex run."""

    lines = [
        "The previous run did not fully satisfy the planner rules.",
        "Please open PLANER.md again and make sure the required files are updated.",
    ]
    if missing_updates:
        lines.append(f"Files that did not change: {', '.join(missing_updates)}")
    if garbled_documents:
        lines.append(f"Files with garbled text: {', '.join(garbled_documents)}")
    lines.extend(
        [
            "Do not leave the issue unresolved.",
            "If a file still needs no change, state the reason clearly in the final response.",
            "Prefer minimal, maintainable edits.",
        ]
    )
    return "\n".join(lines)


def run_codex_cli(target_directory: Path, prompt: str) -> subprocess.CompletedProcess[str]:
    """Run Codex CLI in the target project directory."""

    command = [
        "codex",
        "exec",
        "--cd",
        str(target_directory),
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        prompt,
    ]
    logger.info("Running Codex planner command in %s", target_directory)
    return subprocess.run(
        command,
        cwd=target_directory,
        capture_output=True,
        text=True,
        check=False,
    )


def collect_document_snapshots(target_directory: Path) -> Dict[str, DocumentSnapshot]:
    """Collect file hashes and garble state for the tracked documents."""

    return {filename: snapshot_document(target_directory / filename) for filename in PLANNED_DOCUMENTS}


def snapshot_document(path: Path) -> DocumentSnapshot:
    """Snapshot a document for before/after comparison."""

    if not path.exists():
        return DocumentSnapshot(path=path, exists=False, sha256=None, size=None, has_garble=False)

    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return DocumentSnapshot(path=path, exists=True, sha256=None, size=None, has_garble=True)

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return DocumentSnapshot(
            path=path,
            exists=True,
            sha256=hashlib.sha256(raw_bytes).hexdigest(),
            size=len(raw_bytes),
            has_garble=True,
        )

    return DocumentSnapshot(
        path=path,
        exists=True,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        size=len(raw_bytes),
        has_garble=contains_garble(text),
    )


def contains_garble(text: str) -> bool:
    """Detect common text corruption patterns."""

    return any(pattern in text for pattern in GARBLED_PATTERNS)


def find_missing_updates(
    before_snapshots: Dict[str, DocumentSnapshot],
    after_snapshots: Dict[str, DocumentSnapshot],
) -> List[str]:
    """Return tracked documents whose content did not change."""

    missing: List[str] = []
    for filename in PLANNED_DOCUMENTS:
        before = before_snapshots[filename]
        after = after_snapshots[filename]
        if not after.exists:
            missing.append(filename)
            continue
        if before.exists and before.sha256 == after.sha256:
            missing.append(filename)
    return missing


def find_garbled_documents(snapshots: Dict[str, DocumentSnapshot]) -> List[str]:
    """Return tracked documents that appear to contain corrupted text."""

    return [filename for filename, snapshot in snapshots.items() if snapshot.has_garble]


def snapshots_to_json(snapshots: Dict[str, DocumentSnapshot]) -> Dict[str, Dict[str, Any]]:
    """Serialize snapshots for workflow state."""

    return {
        filename: {
            "path": str(snapshot.path),
            "exists": snapshot.exists,
            "sha256": snapshot.sha256,
            "size": snapshot.size,
            "has_garble": snapshot.has_garble,
        }
        for filename, snapshot in snapshots.items()
    }


def summarize_failures(missing_updates: List[str], garbled_documents: List[str], last_error: str) -> str:
    """Produce a concise human-readable failure message."""

    parts: List[str] = []
    if missing_updates:
        parts.append(f"Missing updates: {', '.join(missing_updates)}")
    if garbled_documents:
        parts.append(f"Garbled documents: {', '.join(garbled_documents)}")
    cleaned_error = last_error.strip()
    if cleaned_error:
        parts.append(f"Codex stderr: {cleaned_error[:1200]}")
    if not parts:
        parts.append("Harness planner did not finish successfully")
    return "; ".join(parts)

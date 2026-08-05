"""Node handlers for the harness planner agent."""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig

from app.agents.harness.harness_initializer.nodes import resolve_target_directory, resolve_template_directory
from app.agents.harness.harness_planner.state import HarnessPlannerState


logger = logging.getLogger(__name__)
TRACKED_DOCUMENTS = ("AGENT.md", "FEATURES.md", "PROGRESS.md", "DECISIONS.md", "ARCHITECTURE.md")
REQUIRED_UPDATE_DOCUMENTS = ("PROGRESS.md",)
OPTIONAL_DOCUMENTS = ("AGENT.md", "FEATURES.md", "DECISIONS.md", "ARCHITECTURE.md")
READ_ONLY_DOCUMENTS = ("PLANER.md",)
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
        before_project_files = snapshot_project_files(target_directory)
        attempts: List[Dict[str, Any]] = []
        last_stderr = ""

        prompt = build_codex_prompt(
            target_directory,
            template_directory,
            before_snapshots,
            state.get("checker_results") or {},
        )
        for attempt_index in range(1, MAX_CODEX_ATTEMPTS + 1):
            result = run_codex_cli(target_directory, prompt)
            after_snapshots = collect_document_snapshots(target_directory)
            after_project_files = snapshot_project_files(target_directory)
            missing_updates = find_missing_updates(before_snapshots, after_snapshots)
            unchanged_without_reason = find_unchanged_without_reason(
                before_snapshots,
                after_snapshots,
                result.stdout,
            )
            garbled_documents = find_garbled_documents(after_snapshots)
            forbidden_changes = find_forbidden_changes(
                before_project_files, after_project_files
            )

            attempts.append(
                {
                    "attempt": attempt_index,
                    "exit_code": result.returncode,
                    "missing_updates": missing_updates,
                    "unchanged_without_reason": unchanged_without_reason,
                    "garbled_documents": garbled_documents,
                    "forbidden_changes": forbidden_changes,
                    "stdout": result.stdout[-8000:],
                    "stderr": result.stderr[-8000:],
                }
            )
            last_stderr = result.stderr

            if (
                result.returncode == 0
                and not missing_updates
                and not unchanged_without_reason
                and not garbled_documents
                and not forbidden_changes
            ):
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

            prompt = build_retry_prompt(missing_updates, unchanged_without_reason, garbled_documents, forbidden_changes)

        final_after_snapshots = collect_document_snapshots(target_directory)
        final_missing_updates = find_missing_updates(before_snapshots, final_after_snapshots)
        final_unchanged_without_reason = find_unchanged_without_reason(
            before_snapshots,
            final_after_snapshots,
            attempts[-1].get("stdout", "") if attempts else "",
        )
        final_garbled_documents = find_garbled_documents(final_after_snapshots)
        final_project_files = snapshot_project_files(target_directory)
        final_forbidden_changes = find_forbidden_changes(
            before_project_files, final_project_files
        )
        logger.warning(
            "Harness planner ended with unresolved documents: missing=%s unchanged_without_reason=%s garbled=%s forbidden=%s",
            final_missing_updates,
            final_unchanged_without_reason,
            final_garbled_documents,
            final_forbidden_changes,
        )
        return {
            "status": "error",
            "error": summarize_failures(
                final_missing_updates,
                final_unchanged_without_reason,
                final_garbled_documents,
                final_forbidden_changes,
                last_stderr,
            ),
            "results": {
                "target_directory": str(target_directory),
                "template_directory": str(template_directory),
                "before_snapshots": snapshots_to_json(before_snapshots),
                "after_snapshots": snapshots_to_json(final_after_snapshots),
                "forbidden_changes": final_forbidden_changes,
                "attempts": attempts,
                "codex_status": "failed",
            },
        }


def build_codex_prompt(
    target_directory: Path,
    template_directory: Path,
    snapshots: Dict[str, DocumentSnapshot],
    checker_results: Dict[str, Any],
) -> str:
    """Build the initial Codex prompt for the planner stage."""

    planned_status = [
        f"- {name}: {'exists' if snapshot.exists else 'missing'}"
        for name, snapshot in snapshots.items()
    ]
    checker_report = str(checker_results.get("remake_report") or "").strip()
    checker_context = (
        [
            "The previous harness_checker rejected the implementation and requested remake.",
            f"Checker report: {checker_report}",
            "Turn this report into a concrete repair plan in PROGRESS.md for harness_worker.",
        ]
        if checker_report
        else []
    )
    return "\n".join(
        [
            "You are harness_planner.",
            f"Work inside: {target_directory}",
            f"Harness templates: {template_directory}",
            "Read PLANER.md in the current project before making any changes.",
            "Update only AGENT.md, FEATURES.md, PROGRESS.md, DECISIONS.md, and ARCHITECTURE.md.",
            "Read PLANER.md, but never modify PLANER.md or any file outside the five allowed documents.",
            "PROGRESS.md must be updated in this planning pass.",
            "FEATURES.md must be updated when there is a new feature or feature status change; otherwise it may remain unchanged only with an explicit reason.",
            "DECISIONS.md, AGENT.md, and ARCHITECTURE.md may remain unchanged only when no new decision, project information, or architecture change applies, with an explicit reason.",
            "Keep all tracked documents in clean UTF-8 and avoid garbled text.",
            "For every unchanged optional document, include exactly one final response line: HARNESS_DOCUMENT_DECISION: <filename>=unchanged; reason=<具体原因>",
            *checker_context,
            "Tracked document status before the run:",
            *planned_status,
            "Any change outside the five allowed files is a failure and must be corrected.",
        ]
    )


def build_retry_prompt(
    missing_updates: List[str],
    unchanged_without_reason: List[str],
    garbled_documents: List[str],
    forbidden_changes: List[str],
) -> str:
    """Build a stricter follow-up prompt after an incomplete Codex run."""

    lines = [
        "The previous run did not fully satisfy the planner rules.",
        "Please open PLANER.md again and complete the planning pass.",
    ]
    if missing_updates:
        lines.append(f"Files that did not change: {', '.join(missing_updates)}")
    if unchanged_without_reason:
        lines.append(
            "These unchanged documents have no explicit valid reason in the final response: "
            + ", ".join(unchanged_without_reason)
        )
    if garbled_documents:
        lines.append(f"Files with garbled text: {', '.join(garbled_documents)}")
    if forbidden_changes:
        lines.append(f"Files that must not have been changed: {', '.join(forbidden_changes)}")
    lines.extend(
        [
            "Do not leave the issue unresolved.",
            "If an optional document truly needs no change, leave it unchanged and provide the required HARNESS_DOCUMENT_DECISION line with a concrete reason.",
            "Revert every forbidden change, then update only the five allowed files.",
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


def snapshot_project_files(target_directory: Path) -> Dict[str, str]:
    """Hash project files so the planner can enforce its write boundary."""

    snapshots: Dict[str, str] = {}
    for path in target_directory.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        relative_path = path.relative_to(target_directory).as_posix()
        try:
            snapshots[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
    return snapshots


def find_forbidden_changes(
    before_files: Dict[str, str], after_files: Dict[str, str]
) -> List[str]:
    """Return files changed outside the planner's five allowed documents."""

    allowed_files = set(TRACKED_DOCUMENTS)
    changed_files = {
        filename
        for filename in set(before_files) | set(after_files)
        if before_files.get(filename) != after_files.get(filename)
    }
    return sorted(changed_files - allowed_files)


def collect_document_snapshots(target_directory: Path) -> Dict[str, DocumentSnapshot]:
    """Collect file hashes and garble state for the tracked documents."""

    return {filename: snapshot_document(target_directory / filename) for filename in TRACKED_DOCUMENTS}


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


DOCUMENT_DECISION_PATTERN = re.compile(
    r"HARNESS_DOCUMENT_DECISION:\s*(AGENT\.md|FEATURES\.md|DECISIONS\.md|ARCHITECTURE\.md)\s*=\s*unchanged\s*;\s*reason\s*=\s*(.+)",
    re.IGNORECASE,
)


def find_unchanged_without_reason(
    before_snapshots: Dict[str, DocumentSnapshot],
    after_snapshots: Dict[str, DocumentSnapshot],
    output: str,
) -> List[str]:
    """Require a concrete Codex explanation for every unchanged optional document."""

    decisions = {
        match.group(1).upper(): match.group(2).strip()
        for match in DOCUMENT_DECISION_PATTERN.finditer(output or "")
        if match.group(2).strip()
    }
    missing_reasons: List[str] = []
    for filename in OPTIONAL_DOCUMENTS:
        before = before_snapshots[filename]
        after = after_snapshots[filename]
        if before.exists and after.exists and before.sha256 == after.sha256:
            if filename.upper() not in decisions:
                missing_reasons.append(filename)
    return missing_reasons


def find_missing_updates(
    before_snapshots: Dict[str, DocumentSnapshot],
    after_snapshots: Dict[str, DocumentSnapshot],
) -> List[str]:
    """Return tracked documents whose content did not change."""

    missing: List[str] = []
    for filename in REQUIRED_UPDATE_DOCUMENTS:
        before = before_snapshots[filename]
        after = after_snapshots[filename]
        if not after.exists or (before.exists and before.sha256 == after.sha256):
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


def summarize_failures(
    missing_updates: List[str],
    unchanged_without_reason: List[str],
    garbled_documents: List[str],
    forbidden_changes: List[str],
    last_error: str,
) -> str:
    """Produce a concise human-readable failure message."""

    parts: List[str] = []
    if missing_updates:
        parts.append(f"Missing updates: {', '.join(missing_updates)}")
    if unchanged_without_reason:
        parts.append(
            "Unchanged documents without reasons: "
            + ", ".join(unchanged_without_reason)
        )
    if garbled_documents:
        parts.append(f"Garbled documents: {', '.join(garbled_documents)}")
    if forbidden_changes:
        parts.append(f"Forbidden changes: {', '.join(forbidden_changes)}")
    cleaned_error = last_error.strip()
    if cleaned_error:
        parts.append(f"Codex stderr: {cleaned_error[:1200]}")
    if not parts:
        parts.append("Harness planner did not finish successfully")
    return "; ".join(parts)

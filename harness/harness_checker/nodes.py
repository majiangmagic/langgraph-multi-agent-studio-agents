"""Node handlers for the Harness checker agent."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List


from app.agents.harness.harness_checker.state import HarnessCheckerState
from app.agents.harness.harness_initializer.nodes import resolve_target_directory

GARBLED_PATTERNS = (
    "\ufffd",
    "???",
    "\u951b",
    "\u9286",
    "\u9225",
    "\u9428\u52ec",
    "\u93c2\u56e6\u6b22",
)
CHECK_RESULT_PATTERN = re.compile(
    r"HARNESS_CHECK_RESULT:\s*(passed|remake)",
    re.IGNORECASE,
)
CHECK_SUMMARY_PATTERN = re.compile(
    r"HARNESS_CHECK_SUMMARY:\s*(.+)",
    re.IGNORECASE,
)


class FunctionalityCheckerNode:
    """Use Codex CLI and CHECKER.md to validate the implemented feature."""

    def __call__(self, state: HarnessCheckerState) -> Dict[str, Any]:
        target_directory = resolve_target_directory(state)
        checker_path = target_directory / "CHECKER.md"
        if not checker_path.is_file():
            return build_remake_result(
                state,
                target_directory,
                "CHECKER.md does not exist; the feature cannot be validated.",
                "functionality_checker",
            )
        try:
            checker_text = checker_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return build_remake_result(
                state,
                target_directory,
                "CHECKER.md is not valid UTF-8.",
                "functionality_checker",
            )
        if not checker_text.strip():
            return build_remake_result(
                state,
                target_directory,
                "CHECKER.md is empty; the feature cannot be validated.",
                "functionality_checker",
            )

        result = run_codex_check(target_directory)
        check_result = parse_check_result(result.stdout)
        summary = parse_check_summary(result.stdout)
        validation = {
            "exit_code": result.returncode,
            "check_result": check_result,
            "summary": summary,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
        }
        if result.returncode != 0 or check_result != "passed":
            report = summary or (
                summarize_codex_failure(result)
                if result.returncode != 0
                else "harness_checker did not return HARNESS_CHECK_RESULT: passed; planner must remake and revalidate the feature."
            )
            return build_remake_result(
                state,
                target_directory,
                report,
                "functionality_checker",
                validation=validation,
            )

        return {
            "status": "checking",
            "error": None,
            "validation": validation,
            "results": {
                **(state.get("results") or {}),
                "target_directory": str(target_directory),
                "validation": validation,
                "remake_required": False,
                "remake_report": "",
                "check_phase": "functionality_checker",
            },
        }


class OtherCheckNode:
    """Check every Markdown file under the project for garbled text."""

    def __call__(self, state: HarnessCheckerState) -> Dict[str, Any]:
        target_directory = resolve_target_directory(state)
        issues = check_all_markdown_files(target_directory)
        if issues:
            report = "Markdown garble check failed: " + "; ".join(
                f"{issue['path']}: {issue['reason']}" for issue in issues[:20]
            )
            return build_remake_result(
                state,
                target_directory,
                report,
                "other_check",
                markdown_issues=issues,
            )

        return {
            "status": "verified",
            "error": None,
            "markdown_issues": [],
            "results": {
                **(state.get("results") or {}),
                "target_directory": str(target_directory),
                "markdown_files_checked": count_markdown_files(target_directory),
                "markdown_issues": [],
                "remake_required": False,
                "remake_report": "",
                "check_phase": "other_check",
            },
        }


class GitCheckpointCreatorNode:
    """Create a local Git checkpoint after all checks pass."""

    def __call__(self, state: HarnessCheckerState) -> Dict[str, Any]:
        target_directory = resolve_target_directory(state)
        repository_check = run_git(
            target_directory,
            ["rev-parse", "--is-inside-work-tree"],
            allow_exit_codes={0, 128},
        )
        if repository_check.returncode != 0 or repository_check.stdout.strip() != "true":
            return build_remake_result(
                state,
                target_directory,
                "The project has no local Git repository, so the verified work cannot be archived.",
                "git_checkpoint_creator",
            )

        run_git(target_directory, ["add", "-A"])
        run_git(
            target_directory,
            [
                "-c",
                "user.name=Harness Checker",
                "-c",
                "user.email=harness-checker@localhost",
                "commit",
                "--allow-empty",
                "-m",
                "Archive verified Harness work",
            ],
        )
        checkpoint_created = True
        commit_hash = run_git(target_directory, ["rev-parse", "HEAD"]).stdout.strip()
        return {
            "status": "complete",
            "error": None,
            "results": {
                **(state.get("results") or {}),
                "target_directory": str(target_directory),
                "checkpoint_created": checkpoint_created,
                "checkpoint_commit": commit_hash,
                "remake_required": False,
                "remake_report": "",
                "check_phase": "git_checkpoint_creator",
            },
        }


def check_all_markdown_files(target_directory: Path) -> List[Dict[str, str]]:
    """Return encoding or garble issues found in every project Markdown file."""

    if not target_directory.exists() or not target_directory.is_dir():
        return [{"path": str(target_directory), "reason": "project directory does not exist"}]

    issues: List[Dict[str, str]] = []
    for path in iter_markdown_files(target_directory):
        relative_path = path.relative_to(target_directory).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            issues.append({"path": relative_path, "reason": "not valid UTF-8"})
            continue
        matched_pattern = next((pattern for pattern in GARBLED_PATTERNS if pattern in text), None)
        if matched_pattern is not None:
            issues.append(
                {
                    "path": relative_path,
                    "reason": f"contains garbled text pattern {matched_pattern!r}",
                }
            )
    return issues


def iter_markdown_files(target_directory: Path):
    """Yield Markdown files while excluding Git internals."""

    for path in target_directory.rglob("*.md"):
        if path.is_file() and ".git" not in path.parts:
            yield path


def count_markdown_files(target_directory: Path) -> int:
    """Count Markdown files included in other_check."""

    return sum(1 for _ in iter_markdown_files(target_directory))


def build_checker_prompt() -> str:
    """Build the Codex CLI prompt used for functional validation."""

    return "\n".join(
        [
            "You are harness_checker.",
            "Read CHECKER.md before doing anything else and follow it as the mandatory validation contract.",
            "Read PROGRESS.md to understand what harness_worker claims to have completed.",
            "Read FEATURES.md through the Harness scripts when CHECKER.md requires it.",
            "Run the required unit, integration, and end-to-end checks in order when those layers exist.",
            "Do not implement fixes and do not hide failures. Your job is validation and reporting.",
            "You may update Harness status documents only when CHECKER.md explicitly requires it.",
            "Do not create a Git commit; the workflow creates the checkpoint after every check passes.",
            "End with exactly these two lines:",
            "HARNESS_CHECK_RESULT: passed or remake",
            "HARNESS_CHECK_SUMMARY: concise evidence, failed checks, and what planner must remake",
        ]
    )


def run_codex_check(target_directory: Path) -> subprocess.CompletedProcess[str]:
    """Run Codex CLI to validate the completed feature."""

    return subprocess.run(
        [
            "codex",
            "exec",
            "--cd",
            str(target_directory),
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            build_checker_prompt(),
        ],
        cwd=target_directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def parse_check_result(output: str) -> str:
    """Parse the required checker result marker."""

    matches = list(CHECK_RESULT_PATTERN.finditer(output or ""))
    return matches[-1].group(1).lower() if matches else "remake"


def parse_check_summary(output: str) -> str:
    """Parse the checker report forwarded to the planner."""

    matches = list(CHECK_SUMMARY_PATTERN.finditer(output or ""))
    return matches[-1].group(1).strip() if matches else ""


def build_remake_result(
    state: HarnessCheckerState,
    target_directory: Path,
    report: str,
    phase: str,
    validation: Dict[str, Any] | None = None,
    markdown_issues: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    """Return a bounded remake request for the workflow planner."""

    remake_count = int(state.get("remake_count") or 0) + 1
    results = {
        **(state.get("results") or {}),
        "target_directory": str(target_directory),
        "remake_required": True,
        "remake_report": report,
        "remake_count": remake_count,
        "check_phase": phase,
    }
    if validation is not None:
        results["validation"] = validation
    if markdown_issues is not None:
        results["markdown_issues"] = markdown_issues
    return {
        "status": "remake",
        "error": report,
        "remake_count": remake_count,
        "validation": validation or {},
        "markdown_issues": markdown_issues or [],
        "results": results,
    }


def run_git(
    target_directory: Path,
    arguments: List[str],
    allow_exit_codes: set[int] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a local Git command and validate its exit code."""

    result = subprocess.run(
        ["git", *arguments],
        cwd=target_directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    accepted = allow_exit_codes or {0}
    if result.returncode not in accepted:
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        raise RuntimeError(f"Git command failed ({' '.join(arguments)}): {output}")
    return result


def summarize_codex_failure(result: subprocess.CompletedProcess[str]) -> str:
    """Create a concise validation failure report."""

    output = (result.stderr or result.stdout or "").strip()
    if output:
        return output[:2000]
    return f"Harness checker Codex execution failed with exit code {result.returncode}"

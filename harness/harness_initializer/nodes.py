"""Node handlers for the harness initializer agent."""

from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from app.agents.harness.harness_initializer.spec import SCRIPT_CREATED_DOCUMENTS, HARNESS_TEMPLATE_DIRECTORY, REQUIRED_DOCUMENTS
from app.agents.harness.harness_initializer.state import HarnessInitializerState


CORE_SOURCE_EXTENSIONS = {
    ".py", ".pyw", ".pyx", ".pyi",
    ".c", ".h", ".cc", ".cp", ".cxx", ".cpp", ".c++",
    ".hh", ".hpp", ".hxx", ".h++", ".ipp", ".inl",
    ".rs", ".go", ".java", ".kt", ".kts", ".groovy", ".scala",
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".cs", ".fs", ".fsx", ".vb", ".swift", ".m", ".mm",
    ".dart", ".rb", ".php", ".pl", ".pm", ".sh", ".bash",
    ".zsh", ".fish", ".ps1", ".bat", ".cmd", ".lua", ".r",
    ".ex", ".exs", ".erl", ".hrl", ".clj", ".cljs", ".lisp",
    ".sol", ".zig", ".nim", ".hs", ".lhs", ".ml", ".mli",
    ".pas", ".pp", ".asm", ".s", ".jl", ".v", ".vh", ".vhd",
    ".vhdl", ".sql", ".proto", ".graphql", ".gql", ".tf",
    ".hcl", ".html", ".htm", ".vue", ".svelte", ".astro",
    ".css", ".scss", ".sass", ".less", ".styl",
}
PROJECT_MARKER_NAMES = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "pipfile", "poetry.lock", "uv.lock", "tox.ini", "pytest.ini",
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "bun.lockb", "tsconfig.json", "cargo.toml", "cargo.lock",
    "go.mod", "go.sum", "pom.xml", "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts", "gradlew", "cmakelists.txt",
    "makefile", "meson.build", "configure.ac", "configure", "composer.json",
    "gemfile", "gemfile.lock", "pubspec.yaml", "mix.exs", "rebar.config",
    "global.json", "directory.build.props", "directory.build.targets",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "compose.yml", "compose.yaml", "justfile", "taskfile.yml",
    "taskfile.yaml", "rakefile", "jenkinsfile", "vagrantfile",
    "build", "workspace", "flake.nix", "shell.nix", "deno.json",
    "deno.jsonc",
}
PROJECT_MARKER_PATTERNS = (
    "*.csproj", "*.fsproj", "*.vbproj", "*.sln", "*.vcxproj", "*.pro",
    "build.*", "vite.config.*", "webpack.config.*", "rollup.config.*",
    "next.config.*", "nuxt.config.*", "astro.config.*", "svelte.config.*",
)
IGNORED_SOURCE_DIRECTORIES = {
    ".git", ".svn", ".hg", "node_modules", "bower_components", "vendor",
    "third_party", "external", "deps", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", "out", "target", "bin", "obj", "coverage",
    "htmlcov", ".cache", "tmp", "temp", "logs", ".next", ".nuxt",
    ".svelte-kit", ".gradle", ".idea", ".vscode",
}
IGNORED_SOURCE_PATTERNS = ("*.min.js", "*.map", "*.bundle.js", "*.generated.*", "*.g.cs", "*.designer.cs")
SOURCE_LANGUAGE_BY_EXTENSION = {
    ".py": "Python", ".pyw": "Python", ".pyx": "Python", ".pyi": "Python",
    ".c": "C", ".h": "C/C++", ".cc": "C++", ".cp": "C++", ".cxx": "C++", ".cpp": "C++", ".c++": "C++",
    ".hpp": "C++", ".rs": "Rust", ".go": "Go", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".cs": "C#", ".fs": "F#", ".swift": "Swift",
    ".m": "Objective-C", ".mm": "Objective-C++", ".dart": "Dart", ".rb": "Ruby", ".php": "PHP",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".fish": "Shell", ".ps1": "PowerShell",
    ".bat": "Batch", ".cmd": "Batch", ".lua": "Lua", ".r": "R", ".ex": "Elixir", ".exs": "Elixir",
    ".erl": "Erlang", ".clj": "Clojure", ".cljs": "ClojureScript", ".sol": "Solidity",
    ".zig": "Zig", ".nim": "Nim", ".hs": "Haskell", ".lhs": "Haskell", ".ml": "OCaml",
    ".mli": "OCaml", ".pas": "Pascal", ".pp": "Pascal", ".asm": "Assembly", ".s": "Assembly",
    ".jl": "Julia", ".sql": "SQL", ".proto": "Protocol Buffers", ".graphql": "GraphQL",
    ".gql": "GraphQL", ".tf": "Terraform", ".hcl": "HCL",
    ".html": "HTML", ".htm": "HTML", ".vue": "Vue", ".svelte": "Svelte", ".astro": "Astro",
    ".css": "CSS", ".scss": "SCSS", ".sass": "Sass", ".less": "Less", ".styl": "Stylus",
}


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
        source_inspection = inspect_existing_source_code(target_directory)
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
                    "source_inspection": source_inspection,
                },
                "created_files": state.get("created_files", []),
                "created_directories": state.get("created_directories", []),
                "git_initialized": False,
                "git_commit": None,
                "harness_copied": False,
            }
        clarification_answer = state.get("clarification_answer")
        original_user_input = str(state.get("user_input") or "").strip()
        enhanced_user_input = append_existing_code_context_task(
            original_user_input, source_inspection
        )
        source_text = "\n".join(
            value
            for value in (original_user_input, clarification_answer)
            if value and str(value).strip()
        )
        if source_inspection["has_source_code"]:
            input_sufficient = True
            missing_information: List[str] = []
        else:
            input_sufficient, missing_information = assess_project_context(
                source_text, state.get("workflow_inputs") or {}
            )

        return {
            "target_directory": str(target_directory),
            "harness_template_directory": str(template_directory),
            "user_input": enhanced_user_input,
            "should_initialize": True,
            "has_existing_source_code": source_inspection["has_source_code"],
            "initialization_mode": source_inspection["initialization_mode"],
            "historical_context_required": source_inspection["has_source_code"],
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
                "source_inspection": source_inspection,
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
    """Create the initial local Git repository when it does not exist."""

    def __call__(
        self,
        state: HarnessInitializerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        if not state.get("should_initialize"):
            return {}

        target_directory = resolve_target_directory(state)
        target_directory.mkdir(parents=True, exist_ok=True)
        repository_created = not (target_directory / ".git").exists()
        if repository_created:
            run_git_command(target_directory, ["init"])
            run_git_command(target_directory, ["add", "-A"])
            run_git_command(
                target_directory,
                [
                    "-c", "user.name=Harness Initializer",
                    "-c", "user.email=harness-initializer@localhost",
                    "commit", "-m", "Initialize local Harness repository",
                ],
            )

        return {
            "git_initialized": True,
            "status": "working",
            "results": {
                **(state.get("results") or {}),
                "git_repository_created": repository_created,
                "initialization_phase": "git_repo_creator",
            },
        }


class GitRepoRefresherNode:
    """Restore the project to the committed clean baseline before continuing."""

    def __call__(
        self,
        state: HarnessInitializerState,
        config: RunnableConfig | None = None,
    ) -> Dict[str, Any]:
        target_directory = resolve_target_directory(state)
        run_git_command(target_directory, ["reset", "--hard", "HEAD"])
        run_git_command(target_directory, ["clean", "-fdx"])

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
                    "context": "\u6587\u4ef6\u548c Git \u57fa\u7ebf\u5df2\u521b\u5efa\uff0c\u8bf7\u8865\u5145\u9879\u76ee\u4fe1\u606f\uff0c\u6062\u590d\u540e\u5c06\u8fdb\u5165 harness_planner\u3002",
                })
                or ""
            ).strip()

        return {
            "clarification_answer": clarification_answer,
            "status": "complete",
            "results": {
                **(state.get("results") or {}),
                "git_working_tree_clean": True,
                "initialization_phase": "git_repo_refresher",
            },
        }


def run_git_command(
    target_directory: Path, arguments: List[str]
) -> subprocess.CompletedProcess[str]:
    """Run a Git command and fail before the workflow can continue."""

    result = subprocess.run(
        ["git", *arguments],
        cwd=target_directory,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        raise RuntimeError(f"Git command failed ({' '.join(arguments)}): {output}")
    return result




def inspect_existing_source_code(target_directory: Path) -> Dict[str, Any]:
    """Inspect project source files and project markers outside ignored directories."""

    if not target_directory.exists():
        return build_source_inspection_result([], [], [], "none")
    if not target_directory.is_dir():
        raise ValueError(f"Target path is not a directory: {target_directory}")

    source_files: List[str] = []
    project_markers: List[str] = []
    source_languages = set()
    for directory, directory_names, filenames in os.walk(target_directory, topdown=True):
        directory_names[:] = sorted(
            name for name in directory_names
            if name.casefold() not in IGNORED_SOURCE_DIRECTORIES
        )
        current_directory = Path(directory)
        for filename in sorted(filenames, key=str.casefold):
            path = current_directory / filename
            relative_path = path.relative_to(target_directory)
            if any(part.casefold() in IGNORED_SOURCE_DIRECTORIES for part in relative_path.parts):
                continue
            lower_name = filename.casefold()
            if lower_name in PROJECT_MARKER_NAMES or any(
                fnmatch.fnmatch(lower_name, pattern.casefold())
                for pattern in PROJECT_MARKER_PATTERNS
            ):
                project_markers.append(relative_path.as_posix())
            if path.suffix.casefold() not in CORE_SOURCE_EXTENSIONS:
                continue
            if any(fnmatch.fnmatch(lower_name, pattern.casefold()) for pattern in IGNORED_SOURCE_PATTERNS):
                continue
            source_files.append(relative_path.as_posix())
            language = SOURCE_LANGUAGE_BY_EXTENSION.get(path.suffix.casefold())
            if language:
                source_languages.add(language)

    source_files = sorted(source_files, key=str.casefold)
    project_markers = sorted(project_markers, key=str.casefold)
    confidence = "high" if source_files else ("possible" if project_markers else "none")
    return build_source_inspection_result(
        source_files,
        project_markers,
        sorted(source_languages),
        confidence,
    )


def build_source_inspection_result(
    source_files: List[str],
    project_markers: List[str],
    source_languages: List[str],
    confidence: str,
) -> Dict[str, Any]:
    """Create the serializable source inspection result."""

    has_source_code = bool(source_files)
    return {
        "has_source_code": has_source_code,
        "source_code_files": source_files[:200],
        "source_code_file_count": len(source_files),
        "project_markers": project_markers[:100],
        "source_languages": source_languages,
        "detection_confidence": confidence,
        "initialization_mode": "existing_code_bootstrap" if has_source_code else "fresh_project",
    }


def append_existing_code_context_task(
    user_input: str,
    source_inspection: Dict[str, Any],
) -> str:
    """Append the historical-context task when initialization finds source code."""

    if not source_inspection.get("has_source_code"):
        return user_input
    task = """

[Existing code project initialization task]
The project is not empty; the initialization scan found source code.
During the Planner stage, also complete these tasks:
1. Analyze the existing code and documents, then add confirmed historical features to FEATURES.md.
2. Add important design decisions that can be confirmed from the code to DECISIONS.md.
3. Mark uncertain information as inferred or pending confirmation; never present it as an explicit user decision.
4. Do not mark unfinished features as completed.
5. Do not modify business code.
6. Record the historical feature and decision review in PROGRESS.md.
""".strip()
    return f"{user_input}\n\n{task}" if user_input else task


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
        or state.get("target_directory")
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

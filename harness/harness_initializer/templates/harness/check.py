from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


TARGET_FILENAMES = ("PROGRESS.md", "DECISIONS.md", "FEATURES.md", "ARCHITECTURE.md")
GARBLED_PATTERNS = (
    "\ufffd",
    "???",
    "\u951b",
    "\u9286",
    "\u9225",
    "\u9428\u52ec",
    "\u93c2\u56e6\u6b22",
)


@dataclass(frozen=True)
class Document:
    """一个被检查的 Harness 文档。"""

    path: Path
    name: str
    content: str


@dataclass(frozen=True)
class CheckIssue:
    """一条检查失败信息。"""

    file_path: Path
    message: str

    def format(self) -> str:
        return f"{self.file_path}: {self.message}"


class harness_check:
    """分别检查 PROGRESS、DECISIONS、FEATURES 和 ARCHITECTURE 文档。"""

    question_mark_run = re.compile(r"\?{3,}")

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()

    def Document_Reader(self, filename: str) -> list[Document]:
        """递归读取指定名称的 Harness 文档。"""
        if not self.root_dir.exists() or not self.root_dir.is_dir():
            raise NotADirectoryError(f"目录不存在: {self.root_dir}")

        documents: list[Document] = []
        for directory, _, filenames in os.walk(self.root_dir):
            if filename not in filenames:
                continue

            path = Path(directory) / filename
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="utf-8", errors="replace")

            documents.append(Document(path=path, name=filename, content=content))

        documents.sort(key=lambda document: str(document.path).casefold())
        return documents

    def Garble_Check(self, document: Document) -> list[CheckIssue]:
        """检查单个文档中是否存在替换字符或连续问号乱码。"""
        has_replacement_character = "\ufffd" in document.content
        has_question_mark_run = self.question_mark_run.search(document.content) is not None
        if has_replacement_character or has_question_mark_run:
            return [CheckIssue(document.path, "检测到乱码")]
        return []

    def Progress_Section_Item_Count(self, content: str, heading: str) -> int:
        """统计 PROGRESS.md 指定三级标题下的列表项数量。"""
        heading_pattern = re.compile(rf"^###\s*{re.escape(heading)}\s*$", re.MULTILINE)
        heading_match = heading_pattern.search(content)
        if heading_match is None:
            return 0

        section_start = heading_match.end()
        section_end = len(content)
        next_heading = re.search(r"^###\s+.+$", content[section_start:], re.MULTILINE)
        if next_heading is not None:
            section_end = section_start + next_heading.start()

        section = content[section_start:section_end]
        item_pattern = re.compile(r"^\s*(?:[-*]\s+\[.*?\]\s+|\d+\.\s+)")
        return sum(1 for line in section.splitlines() if item_pattern.match(line))

    def Progress_Check(self) -> list[CheckIssue]:
        """检查 PROGRESS.md 是否存在、是否乱码以及各区段条目数量。"""
        documents = self.Document_Reader("PROGRESS.md")
        if not documents:
            return [CheckIssue(self.root_dir / "PROGRESS.md", "未找到目标文件")]

        issues: list[CheckIssue] = []
        section_rules = (
            ("已完成", 10),
            ("进行中", 10),
            ("已知问题", 10),
            ("下一步", 10),
        )

        for document in documents:
            issues.extend(self.Garble_Check(document))
            for heading, limit in section_rules:
                count = self.Progress_Section_Item_Count(document.content, heading)
                if count > limit:
                    issues.append(
                        CheckIssue(document.path, f"{heading}条目超过 {limit} 条，当前为 {count} 条")
                    )

        return issues

    def Decisions_Check(self) -> list[CheckIssue]:
        """检查 DECISIONS.md 是否存在以及是否包含乱码。"""
        documents = self.Document_Reader("DECISIONS.md")
        if not documents:
            return [CheckIssue(self.root_dir / "DECISIONS.md", "未找到目标文件")]

        issues: list[CheckIssue] = []
        for document in documents:
            issues.extend(self.Garble_Check(document))
        return issues

    def Features_Check(self) -> list[CheckIssue]:
        """检查 FEATURES.md 是否存在以及是否包含乱码。"""
        documents = self.Document_Reader("FEATURES.md")
        if not documents:
            return [CheckIssue(self.root_dir / "FEATURES.md", "未找到目标文件")]

        issues: list[CheckIssue] = []
        for document in documents:
            issues.extend(self.Garble_Check(document))
        return issues

    def Architecture_Check(self) -> list[CheckIssue]:
        """检查 ARCHITECTURE.md 是否存在以及是否包含乱码。"""
        documents = self.Document_Reader("ARCHITECTURE.md")
        if not documents:
            return [CheckIssue(self.root_dir / "ARCHITECTURE.md", "未找到目标文件")]

        issues: list[CheckIssue] = []
        for document in documents:
            issues.extend(self.Garble_Check(document))
        return issues

    def Other_Check(self) -> list[CheckIssue]:
        """Check every Markdown file for encoding errors and garbled text."""
        if not self.root_dir.exists() or not self.root_dir.is_dir():
            raise NotADirectoryError(f"Project directory does not exist: {self.root_dir}")

        issues: list[CheckIssue] = []
        markdown_files = sorted(
            (
                path
                for path in self.root_dir.rglob("*.md")
                if path.is_file() and ".git" not in path.parts
            ),
            key=lambda path: str(path).casefold(),
        )
        for path in markdown_files:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                issues.append(CheckIssue(path, "File is not valid UTF-8"))
                continue

            matched_pattern = next(
                (pattern for pattern in GARBLED_PATTERNS if pattern in content),
                None,
            )
            if matched_pattern is not None:
                issues.append(CheckIssue(path, f"Garbled text pattern detected: {matched_pattern!r}"))

        return issues

    def All_Check(self) -> list[CheckIssue]:
        """Run all Harness document checks and the project Markdown scan."""
        issues: list[CheckIssue] = []
        issues.extend(self.Progress_Check())
        issues.extend(self.Decisions_Check())
        issues.extend(self.Features_Check())
        issues.extend(self.Architecture_Check())
        issues.extend(self.Other_Check())
        return issues



OPERATIONS = (
    "Progress_Check",
    "Decisions_Check",
    "Features_Check",
    "Architecture_Check",
    "All_Check",
    "other_check",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 Harness 上下文文档")
    parser.add_argument("root_dir", type=Path, help="需要检查的目录")
    parser.add_argument(
        "--operation",
        choices=OPERATIONS,
        default="All_Check",
        help="要执行的检查，默认执行 All_Check",
    )
    return parser


def print_issues(issues: Sequence[CheckIssue]) -> int:
    if not issues:
        print("检查通过")
        return 0

    print("检查未通过，原因如下:")
    for issue in issues:
        print(f"- {issue.format()}")
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    context = harness_check(args.root_dir)

    try:
        if args.operation == "Progress_Check":
            issues = context.Progress_Check()
        elif args.operation == "Decisions_Check":
            issues = context.Decisions_Check()
        elif args.operation == "Features_Check":
            issues = context.Features_Check()
        elif args.operation == "Architecture_Check":
            issues = context.Architecture_Check()
        elif args.operation == "All_Check":
            issues = context.All_Check()
        elif args.operation == "other_check":
            issues = context.Other_Check()
        else:
            parser.error(f"不支持的检查: {args.operation}")
    except NotADirectoryError as error:
        print(error)
        return 2

    return print_issues(issues)


if __name__ == "__main__":
    raise SystemExit(main())

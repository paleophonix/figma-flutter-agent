#!/usr/bin/env python3
"""Count source lines in the repository (gitignore-aware).

Excludes markdown, blank lines, comments, and docstrings.
Reports totals for the whole repo and per top-level directory.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT_MARKER = "(root)"

# Operational / generated trees — not product source (still gitignore-respected).
EXCLUDE_DIRS = frozenset(
    {
        ".debug",
        ".data",
        ".temp",
        ".traces",
        ".worktrees",
        ".repair",
        ".gemini",
        "logs",
    }
)

SKIP_EXTENSIONS = frozenset(
    {
        ".md",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".woff",
        ".woff2",
        ".lock",
        ".log",
    }
)

LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".dart": "dart",
    ".ps1": "hash",
    ".sh": "hash",
    ".yaml": "hash",
    ".yml": "hash",
    ".toml": "hash",
    ".ini": "hash",
    ".js": "c_style",
    ".css": "c_style",
    ".html": "html",
    ".j2": "jinja",
    ".tpl": "jinja",
    ".json": "data",
    ".mdc": "hash",
}


@dataclass
class CountResult:
    """Aggregated line counts."""

    files: int = 0
    lines: int = 0
    by_extension: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parent.parent


def list_git_files(repo_root: Path, *, include_untracked: bool) -> list[Path]:
    """Return paths not excluded by .gitignore (tracked, optionally + untracked)."""
    args = ["git", "ls-files", "--exclude-standard"]
    if include_untracked:
        args.extend(["-c", "-o"])
    else:
        args.append("-c")
    proc = subprocess.run(
        args,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    paths: list[Path] = []
    for line in proc.stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        paths.append(Path(text))
    return paths


def is_excluded_path(rel_path: Path, *, include_json: bool, include_debug: bool) -> bool:
    parts = rel_path.parts
    if parts and parts[0] in EXCLUDE_DIRS and not include_debug:
        return True
    ext = rel_path.suffix.lower()
    if ext in SKIP_EXTENSIONS:
        return True
    if ext == ".json" and not include_json:
        return True
    return ext not in LANGUAGE_BY_EXTENSION


def top_level_bucket(rel_path: Path) -> str:
    parts = rel_path.parts
    if len(parts) <= 1:
        return ROOT_MARKER
    return parts[0]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def python_docstring_lines(source: str) -> set[int]:
    """Line numbers occupied by module/class/function docstrings."""
    lines: set[int] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return lines

    def add_docstring(node: ast.AST) -> None:
        body = getattr(node, "body", None)
        if not body:
            return
        first = body[0]
        if not isinstance(first, ast.Expr):
            return
        value = first.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            end = getattr(first, "end_lineno", first.lineno)
            lines.update(range(first.lineno, end + 1))

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add_docstring(node)
    return lines


def count_python_lines(source: str) -> int:
    import io
    import tokenize

    doc_lines = python_docstring_lines(source)
    counted: set[int] = set()

    try:
        tokens = tokenize.tokenize(io.BytesIO(source.encode("utf-8")).readline)
    except tokenize.TokenError:
        return count_hash_lines(source)

    for tok in tokens:
        if tok.type in {
            tokenize.COMMENT,
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.ENCODING,
            tokenize.ENDMARKER,
            tokenize.INDENT,
            tokenize.DEDENT,
        }:
            continue
        lineno = tok.start[0]
        if lineno in doc_lines:
            continue
        counted.add(lineno)

    return len(counted)


def strip_c_style_keep_code(text: str) -> str:
    """Remove //, ///, and /* */ while preserving newlines for line accounting."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_string: str | None = None
    in_block = False

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_block:
            if ch == "*" and nxt == "/":
                in_block = False
                i += 2
                continue
            if ch == "\n":
                out.append("\n")
            i += 1
            continue

        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue

        if ch in "\"'":
            in_string = ch
            out.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "/":
            if i + 2 < n and text[i + 2] == "/":
                i = text.find("\n", i)
                if i == -1:
                    break
                continue
            i = text.find("\n", i)
            if i == -1:
                break
            continue

        if ch == "/" and nxt == "*":
            in_block = True
            i += 2
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def count_non_empty_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def count_hash_lines(source: str) -> int:
    counted = 0
    for line in source.splitlines():
        stripped = _strip_hash_comment(line)
        if stripped.strip():
            counted += 1
    return counted


def _strip_hash_comment(line: str) -> str:
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "'" and not in_double:
            if in_single and i + 1 < len(line) and line[i + 1] == "'":
                i += 2
                continue
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            if in_double and i + 1 < len(line) and line[i + 1] == '"':
                i += 2
                continue
            in_double = not in_double
            i += 1
            continue
        if ch == "#" and not in_single and not in_double:
            return line[:i]
        i += 1
    return line


def strip_jinja_comments(text: str) -> str:
  text = re.sub(r"\{#.*?#\}", "", text, flags=re.DOTALL)
  text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
  return strip_c_style_keep_code(text)


def count_lines_for_language(language: str, source: str) -> int:
    if language == "python":
        return count_python_lines(source)
    if language == "dart":
        return count_non_empty_lines(strip_c_style_keep_code(source))
    if language == "c_style":
        return count_non_empty_lines(strip_c_style_keep_code(source))
    if language == "hash":
        return count_hash_lines(source)
    if language == "html":
        text = re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)
        return count_non_empty_lines(strip_c_style_keep_code(text))
    if language == "jinja":
        return count_non_empty_lines(strip_jinja_comments(source))
    if language == "data":
        return count_non_empty_lines(source)
    return count_non_empty_lines(source)


def count_file(path: Path) -> int | None:
    language = LANGUAGE_BY_EXTENSION.get(path.suffix.lower())
    if language is None:
        return None
    source = read_text(path)
    return count_lines_for_language(language, source)


def scan_repo(
    repo_root: Path,
    *,
    include_untracked: bool,
    include_json: bool,
    include_debug: bool,
) -> tuple[CountResult, dict[str, CountResult]]:
    total = CountResult()
    by_dir: dict[str, CountResult] = defaultdict(CountResult)

    for rel in list_git_files(repo_root, include_untracked=include_untracked):
        if is_excluded_path(
            rel, include_json=include_json, include_debug=include_debug
        ):
            continue

        abs_path = repo_root / rel
        if not abs_path.is_file():
            continue

        line_count = count_file(abs_path)
        if line_count is None:
            continue

        bucket = top_level_bucket(rel)
        ext = rel.suffix.lower()
        for target in (total, by_dir[bucket]):
            target.files += 1
            target.lines += line_count
            target.by_extension[ext] += line_count

    return total, dict(by_dir)


def print_report(total: CountResult, by_dir: dict[str, CountResult]) -> None:
    width = max((len(name) for name in by_dir), default=len(ROOT_MARKER))
    width = max(width, len("TOTAL"))

    print(f"{'Directory':<{width}}  {'Files':>6}  {'Lines':>8}")
    print(f"{'-' * width}  {'-' * 6}  {'-' * 8}")
    print(f"{'TOTAL':<{width}}  {total.files:>6}  {total.lines:>8}")

    for name in sorted(by_dir, key=lambda k: (-by_dir[k].lines, k.lower())):
        row = by_dir[name]
        print(f"{name:<{width}}  {row.files:>6}  {row.lines:>8}")

    print()
    print("By extension (repo total):")
    for ext, count in sorted(total.by_extension.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {ext:8} {count:>8}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=repo_root_from_script(),
        help="Repository root (default: parent of scripts/).",
    )
    parser.add_argument(
        "--include-untracked",
        action="store_true",
        help="Also count untracked files that are not gitignored.",
    )
    parser.add_argument(
        "--include-json",
        action="store_true",
        help="Include .json data files (excluded by default).",
    )
    parser.add_argument(
        "--include-debug",
        action="store_true",
        help="Include .debug/ and other operational artifact dirs.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    if not (repo_root / ".git").exists():
        print(f"Not a git repository: {repo_root}", file=sys.stderr)
        return 1

    total, by_dir = scan_repo(
        repo_root,
        include_untracked=args.include_untracked,
        include_json=args.include_json,
        include_debug=args.include_debug,
    )
    print_report(total, by_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

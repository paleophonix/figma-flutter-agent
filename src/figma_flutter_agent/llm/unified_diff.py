"""Apply git-style unified diffs to Dart sources (fail-closed)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HUNK_HEADER = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@",
)
_FILE_HEADER = re.compile(r"^(?:---|\+\+\+)\s+")


@dataclass(frozen=True)
class _DiffHunk:
    old_start: int
    lines: tuple[str, ...]


def is_unified_diff_text(text: str) -> bool:
    """Return True when ``text`` looks like a unified diff rather than a full file body."""
    stripped = text.strip()
    if not stripped:
        return False
    if _HUNK_HEADER.search(stripped, re.MULTILINE):
        return True
    if stripped.startswith("--- ") or stripped.startswith("+++ "):
        return True
    body_lines = stripped.splitlines()
    if any(line.startswith("@@") for line in body_lines):
        plus_minus = sum(
            1
            for line in body_lines
            if line.startswith("+") or line.startswith("-") or line.startswith(" ")
        )
        return plus_minus >= 2
    return False


def _split_lines_preserving_newline(source: str) -> list[str]:
    if not source:
        return []
    lines = source.splitlines(keepends=True)
    if source and not source.endswith(("\n", "\r\n")) and lines:
        lines[-1] = lines[-1].rstrip("\r\n")
    return lines


def _join_lines(lines: list[str]) -> str:
    return "".join(lines)


def _line_equal(left: str, right: str) -> bool:
    return left.rstrip("\r\n") == right.rstrip("\r\n")


def _normalize_insert_line(content: str, *, template: str | None) -> str:
    if content.endswith(("\n", "\r\n")):
        return content
    if template and template.endswith("\n"):
        return content + "\n"
    return content


def _parse_hunks(diff_text: str) -> list[_DiffHunk]:
    hunks: list[_DiffHunk] = []
    current_lines: list[str] = []
    old_start = 1

    def _flush() -> None:
        nonlocal current_lines, old_start
        if current_lines:
            hunks.append(_DiffHunk(old_start=old_start, lines=tuple(current_lines)))
        current_lines = []

    for raw_line in diff_text.splitlines():
        if _FILE_HEADER.match(raw_line):
            continue
        if raw_line.startswith("\\ No newline"):
            continue
        header = _HUNK_HEADER.match(raw_line)
        if header:
            _flush()
            old_start = int(header.group(1))
            continue
        if raw_line.startswith(("+", "-")):
            current_lines.append(raw_line)
            continue
        if raw_line.startswith(" "):
            current_lines.append(raw_line)
            continue
        if raw_line == "":
            current_lines.append(" ")
            continue
        if current_lines or old_start > 0:
            current_lines.append(f" {raw_line}")
    _flush()
    return hunks


def apply_unified_diff(base: str, diff_text: str) -> str | None:
    """Apply ``diff_text`` to ``base`` and return patched source, or ``None`` on failure."""
    hunks = _parse_hunks(diff_text)
    if not hunks:
        return None

    lines = _split_lines_preserving_newline(base)
    offset = 0

    for hunk in hunks:
        index = hunk.old_start - 1 + offset
        for hunk_line in hunk.lines:
            if not hunk_line:
                continue
            tag = hunk_line[0]
            content = hunk_line[1:]
            if tag == " ":
                if index >= len(lines):
                    return None
                if not _line_equal(lines[index], content):
                    return None
                index += 1
            elif tag == "-":
                if index >= len(lines):
                    return None
                if not _line_equal(lines[index], content):
                    return None
                del lines[index]
                offset -= 1
            elif tag == "+":
                template = lines[index] if index < len(lines) else (lines[index - 1] if index else None)
                lines.insert(
                    index,
                    _normalize_insert_line(content, template=template),
                )
                index += 1
                offset += 1
            else:
                return None

    return _join_lines(lines)

"""Line-number prefixes for LLM repair prompts (stripped before applying patches)."""

from __future__ import annotations

import re

_LINE_PREFIX_PIPE = re.compile(r"^(?P<num>\d{1,4})\|\s?")
_LINE_PREFIX_COLON = re.compile(r"^(?P<num>\d{1,4}):\s?")
_LINE_PREFIX_ANY = re.compile(r"^(?P<num>\d{1,4})(?:\||:)\s?")


def format_line_numbered_source(source: str) -> str:
    """Prefix each physical line with ``N: `` aligned to dart analyzer line numbers."""
    lines = source.splitlines()
    if not lines:
        return "(empty file)"
    return "\n".join(f"{index}: {line}" for index, line in enumerate(lines, start=1))


def strip_line_number_markers(source: str) -> str:
    """Remove repair line prefixes from Dart source or diff text."""
    if not source:
        return source
    updated_lines: list[str] = []
    for line in source.splitlines(keepends=True):
        body = line
        suffix = ""
        if line.endswith("\n"):
            body = line[:-1]
            suffix = "\n"
        elif line.endswith("\r\n"):
            body = line[:-2]
            suffix = "\r\n"
        stripped = _strip_line_prefix(body)
        updated_lines.append(stripped + suffix)
    return "".join(updated_lines)


def _strip_line_prefix(line: str) -> str:
    updated = line
    while True:
        match = _LINE_PREFIX_ANY.match(updated)
        if match is None:
            return updated
        updated = updated[match.end() :]


def strip_line_number_markers_from_diff(diff_text: str) -> str:
    """Strip accidental line markers from unified-diff context/addition lines."""
    if not diff_text.strip():
        return diff_text
    output: list[str] = []
    for raw in diff_text.splitlines(keepends=True):
        if not raw:
            output.append(raw)
            continue
        newline = ""
        line = raw
        if raw.endswith("\r\n"):
            newline = "\r\n"
            line = raw[:-2]
        elif raw.endswith("\n"):
            newline = "\n"
            line = raw[:-1]
        if line.startswith(("---", "+++", "@@", "\\")):
            output.append(line + newline)
            continue
        prefix = ""
        body = line
        if body[:1] in {" ", "+", "-"}:
            prefix = body[0]
            body = body[1:]
        body = _strip_line_prefix(body)
        output.append(f"{prefix}{body}{newline}")
    return "".join(output)


def format_numbered_excerpt(
    source: str,
    line: int,
    *,
    context_lines: int = 5,
) -> str:
    """Numbered excerpt around a failing analyzer line."""
    lines = source.splitlines()
    if not lines:
        return "(empty file)"
    index = max(0, min(line - 1, len(lines) - 1))
    start = max(0, index - context_lines)
    end = min(len(lines), index + context_lines + 1)
    return "\n".join(f"{number}: {lines[number - 1]}" for number in range(start + 1, end + 1))

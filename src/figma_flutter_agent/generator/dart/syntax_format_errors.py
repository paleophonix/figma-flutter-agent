"""Repairs driven by dart-format parse error locations."""

from __future__ import annotations

import re

_FORMAT_ERROR_LINE_RE = re.compile(r"^line (\d+), column \d+ of ")
_FORMAT_ERROR_INSERT_RE = re.compile(r"line (\d+), column (\d+) of .+?: Expected to find '([^']+)'")


def parse_format_error_line_numbers(errors: tuple[str, ...] | list[str]) -> tuple[int, ...]:
    """Extract unique line numbers from dart format errors."""
    numbers: list[int] = []
    for error in errors:
        match = _FORMAT_ERROR_LINE_RE.match(error.strip())
        if match is not None:
            numbers.append(int(match.group(1)))
    return tuple(dict.fromkeys(numbers))


def append_missing_closers_on_lines(
    source: str,
    line_numbers: tuple[int, ...] | list[int],
) -> str:
    """Append missing ``)]}`` on specific lines."""
    if not line_numbers:
        return source
    from figma_flutter_agent.generator.dart.llm_codegen import _dart_delimiter_stack

    pairs = {"(": ")", "[": "]", "{": "}"}
    lines = source.splitlines()
    for line_no in line_numbers:
        index = line_no - 1
        if not 0 <= index < len(lines):
            continue
        stack = _dart_delimiter_stack(lines[index])
        if not stack:
            continue
        lines[index] = lines[index] + "".join(pairs[opener] for opener in reversed(stack))
    return "\n".join(lines)


def apply_format_parse_error_insertions(
    source: str,
    errors: tuple[str, ...] | list[str],
    *,
    attempt: int = 0,
) -> str:
    """Insert ``]`` / ``,`` / ``;`` at ``dart format`` error columns."""
    insertions: list[tuple[int, int, str]] = []
    for error in errors:
        match = _FORMAT_ERROR_INSERT_RE.search(error)
        if match is None:
            continue
        line_no = int(match.group(1))
        column = int(match.group(2))
        expected = match.group(3)
        if expected in {"]", "}", ")", ",", ";"}:
            insertions.append((line_no, column, expected))
    if not insertions:
        return source

    lines = source.splitlines()
    by_line: dict[int, list[tuple[int, str]]] = {}
    for line_no, column, expected in insertions:
        by_line.setdefault(line_no, []).append((column, expected))

    for line_no, items in by_line.items():
        index = line_no - 1
        if not 0 <= index < len(lines):
            continue
        line = lines[index]
        for column, expected in sorted(items, key=lambda item: item[0], reverse=True):
            position = max(0, column - 1 - attempt)
            if position > len(line):
                line = f"{line}{expected}"
                continue
            if line[position : position + len(expected)] == expected:
                position = min(len(line), position + 1)
                if position > len(line) or line[position : position + len(expected)] == expected:
                    line = f"{line}{expected}"
                    continue
            line = f"{line[:position]}{expected}{line[position:]}"
        lines[index] = line
    return "\n".join(lines)

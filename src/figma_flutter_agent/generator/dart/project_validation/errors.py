"""Parsing and normalization of dart format / dart analyze diagnostic output."""

from __future__ import annotations

import re

_ANALYZE_ERROR_LINE = re.compile(r"^\s*error\s+-", re.MULTILINE)
_ANALYZE_WARNING_LINE = re.compile(r"^\s*warning\s+-", re.MULTILINE)
_FORMAT_PARSE_ERROR_LINE = re.compile(
    r"^line \d+, column \d+ of .+?: .+$",
    re.MULTILINE,
)
_FORMAT_FAILED_PATH_RE = re.compile(
    r"line \d+, column \d+ of .*?(?P<path>lib[/\\][^\s:]+\.dart)",
    re.IGNORECASE,
)
_TEMP_ANALYZE_DIR_RE = re.compile(r"figma-flutter-spec23-[a-z0-9_]+", re.IGNORECASE)
_ABSOLUTE_DART_PATH_RE = re.compile(
    r"(?:[A-Za-z]:)?[/\\][^\s:]+[/\\](?P<basename>[^/\\:]+\.dart)",
    re.IGNORECASE,
)


def parse_format_failed_paths(details: str) -> tuple[str, ...]:
    """Return project-relative ``lib/…`` paths that ``dart format`` could not parse."""
    paths: list[str] = []
    for line in details.splitlines():
        match = _FORMAT_FAILED_PATH_RE.search(line)
        if match is None:
            continue
        paths.append(match.group("path").replace("\\", "/"))
    return tuple(dict.fromkeys(paths))


def parse_format_errors(details: str) -> list[str]:
    """Extract parser diagnostics from ``dart format`` failure output.

    Args:
        details: Combined stdout/stderr from a format invocation.

    Returns:
        Non-empty parser diagnostic lines, if any.
    """
    if "Could not format because the source could not be parsed" not in details:
        return []
    errors: list[str] = []
    for line in details.splitlines():
        stripped = line.strip()
        if _FORMAT_PARSE_ERROR_LINE.match(stripped):
            errors.append(stripped)
    return errors


def collect_analyze_error_lines(details: str, *, detail: str) -> tuple[str, ...]:
    """Merge analyzer and format parser diagnostics into one error tuple."""
    errors = parse_analyze_errors(details) or parse_format_errors(details)
    if errors:
        return tuple(errors)
    return (detail,)


def normalize_analyzer_errors_for_fingerprint(errors: tuple[str, ...]) -> tuple[str, ...]:
    """Strip volatile temp paths so repair loops detect repeated identical failures."""
    normalized: list[str] = []
    for error in errors:
        line = _TEMP_ANALYZE_DIR_RE.sub("<temp>", error)
        line = _ABSOLUTE_DART_PATH_RE.sub(r"\g<basename>", line)
        line = re.sub(
            r"line \d+, column \d+ of ",
            "line N, column M of ",
            line,
            count=1,
        )
        normalized.append(line)
    return tuple(normalized)


def parse_analyze_errors(details: str) -> list[str]:
    """Extract analyzer error lines from ``dart``/``flutter analyze`` output.

    Args:
        details: Combined stdout/stderr from an analyze invocation.

    Returns:
        Non-empty error diagnostic lines, if any.
    """
    errors: list[str] = []
    for line in details.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _ANALYZE_ERROR_LINE.search(stripped):
            errors.append(stripped)
    return errors


def summarize_analyze_diagnostics(
    details: str, *, detail: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split analyzer output into (errors, warnings) tuples.

    Args:
        details: Combined stdout/stderr from an analyze invocation.
        detail: Human-readable label used only when no lines are matched.

    Returns:
        ``(errors, warnings)`` — each a tuple of stripped diagnostic lines.
    """
    errors: list[str] = []
    warnings: list[str] = []
    for line in details.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _ANALYZE_ERROR_LINE.search(stripped):
            errors.append(stripped)
        elif _ANALYZE_WARNING_LINE.search(stripped):
            warnings.append(stripped)
    return tuple(errors), tuple(warnings)

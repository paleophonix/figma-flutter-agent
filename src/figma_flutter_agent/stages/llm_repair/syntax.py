"""Syntax checking and rollback utilities for LLM repair loop."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.project_validation import (
    PlannedAnalyzeOutcome,
    parse_format_failed_paths,
)

CRITICAL_SYNTAX_BROKEN_TAG = "CRITICAL_SYNTAX_BROKEN"

_LIB_DART_PATH_RE = re.compile(r"(lib[/\\][^\s:]+\.dart)", re.IGNORECASE)


def _critical_syntax_broken_directive(
    format_paths: tuple[str, ...],
    *,
    rolled_back: bool,
) -> str:
    target = ", ".join(format_paths) if format_paths else "planned Dart sources"
    if rolled_back:
        return (
            f"{CRITICAL_SYNTAX_BROKEN_TAG}: Rolled back {target} to the last clean snapshot "
            "because the previous repair pass corrupted the file. The diff base is that clean "
            "version — fix the reported analyzer errors with minimal unified-diff hunks only; "
            "do not repeat broken patterns (duplicate `child:`, doubled constructor params)."
        )
    return (
        f"{CRITICAL_SYNTAX_BROKEN_TAG}: dart format could not parse {target}. "
        "The broken source is still on disk — apply minimal unified-diff hunks in place. "
        "Remove duplicate tokens (e.g. `child: child:`), fix constructors; do not rewrite whole files."
    )


def _format_failure_paths_from_outcome(outcome: PlannedAnalyzeOutcome) -> tuple[str, ...]:
    """Resolve ``formatFailedPaths`` from outcome metadata, format log, or error lines."""
    if outcome.format_failed_paths:
        return outcome.format_failed_paths
    paths = parse_format_failed_paths(outcome.analyze_output)
    if paths:
        return paths
    derived: list[str] = []
    for error in outcome.errors:
        match = _LIB_DART_PATH_RE.search(error.replace("\\", "/"))
        if match is not None:
            derived.append(match.group(1).replace("\\", "/"))
    return tuple(dict.fromkeys(derived))


def _repair_patch_has_duplicate_required_this(generation) -> bool:
    """Reject patches that repeat ``{required this.`` within a short window (token guard)."""
    _DUPLICATE_REQUIRED_THIS_RE = re.compile(r"\{required this\.")
    sources = [
        generation.screen_code,
        *[widget.resolved_code() for widget in generation.extracted_widgets],
    ]
    for source in sources:
        if not source:
            continue
        for match in _DUPLICATE_REQUIRED_THIS_RE.finditer(source):
            start = max(0, match.start() - 50)
            window = source[start : match.start() + 100]
            if len(_DUPLICATE_REQUIRED_THIS_RE.findall(window)) >= 2:
                return True
    return False


def _rollback_planned_files_to_snapshot(
    planned: dict[str, str],
    snapshot: dict[str, str],
    paths: tuple[str, ...],
) -> dict[str, str]:
    updated = dict(planned)
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized in snapshot:
            updated[normalized] = snapshot[normalized]
    return updated


def rollback_file_on_syntax_error(
    planned: dict[str, str],
    snapshot: dict[str, str],
    *,
    paths: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Restore planned Dart sources from a pre-repair snapshot."""
    if paths is None:
        paths = tuple(sorted(path.replace("\\", "/") for path in planned if path.endswith(".dart")))
    return _rollback_planned_files_to_snapshot(planned, snapshot, paths)


def _planned_files_have_delimiter_syntax_errors(
    planned: dict[str, str],
    *,
    paths: tuple[str, ...] | None = None,
) -> bool:
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    targets = paths or tuple(
        sorted(path.replace("\\", "/") for path in planned if path.endswith(".dart"))
    )
    return any(validate_dart_delimiters(planned.get(path, "")) is not None for path in targets)


def _syntax_error_count(outcome: PlannedAnalyzeOutcome) -> int:
    """Approximate syntax/format failure severity for stall detection."""
    if _is_syntax_level_analyze_failure(outcome):
        paths = _format_failure_paths_from_outcome(outcome)
        if paths:
            return len(paths)
        return max(len(outcome.errors), 1)
    from figma_flutter_agent.llm.repair_scope import parse_analyze_error_locations

    locations = parse_analyze_error_locations(list(outcome.errors))
    if locations:
        return len(locations)
    markers = (
        "expected",
        "missing",
        "unterminated",
        "can't find",
        "could not format",
        "']'",
        "')'",
    )
    hits = sum(1 for error in outcome.errors if any(m in error.lower() for m in markers))
    return hits if hits else len(outcome.errors)


def _syntax_repair_stalled(history: list[int], stall_limit: int) -> bool:
    if len(history) < stall_limit + 1:
        return False
    window = history[-(stall_limit + 1) :]
    improvements = sum(1 for index in range(stall_limit) if window[index] > window[index + 1])
    return improvements == 0


def _is_syntax_level_analyze_failure(
    outcome: PlannedAnalyzeOutcome,
) -> bool:
    detail = outcome.detail.lower()
    if "dart format failed" in detail:
        return True
    joined = " ".join(outcome.errors).lower()
    return "could not format" in joined or "could not be parsed" in joined

"""Analyzer location parsing and planned-path resolution."""

from __future__ import annotations

import re
from pathlib import Path

from figma_flutter_agent.llm.repair_scope.models import AnalyzeErrorLocation

ANALYZE_ERROR_LOCATION = re.compile(
    r"error\s+-\s+(?P<file>[^\s:]+\.dart):(?P<line>\d+):(?P<col>\d+)\s+-\s+(?P<message>.+)"
)
FORMAT_ERROR_LOCATION = re.compile(
    r"^line (?P<line>\d+), column (?P<col>\d+) of (?P<file>.+\.dart): (?P<message>.+)$"
)


def parse_analyze_error_locations(errors: list[str]) -> list[AnalyzeErrorLocation]:
    """Parse ``dart analyze`` error lines into file/line locations."""
    locations: list[AnalyzeErrorLocation] = []
    for raw in errors:
        stripped = raw.strip()
        match = ANALYZE_ERROR_LOCATION.search(stripped)
        if match is None:
            match = FORMAT_ERROR_LOCATION.match(stripped)
        if match is None:
            continue
        locations.append(
            AnalyzeErrorLocation(
                file_path=match.group("file").replace("\\", "/"),
                line=int(match.group("line")),
                column=int(match.group("col")),
                message=match.group("message").strip(),
                raw=stripped,
            )
        )
    return locations


def resolve_planned_relative_path(file_path: str, planned_files: dict[str, str]) -> str:
    """Map analyzer or formatter paths to a key in ``planned_files``."""
    normalized = file_path.replace("\\", "/")
    if normalized in planned_files:
        return normalized.replace("\\", "/")
    if normalized.startswith("lib/"):
        return normalized
    lib_index = normalized.find("/lib/")
    if lib_index >= 0:
        candidate = normalized[lib_index + 1 :]
        if candidate in planned_files:
            return candidate
    name = Path(normalized).name
    for planned_path in planned_files:
        if Path(planned_path).name == name:
            return planned_path.replace("\\", "/")
    return normalized


def group_errors_by_file(
    errors: list[str],
    locations: list[AnalyzeErrorLocation],
    *,
    planned_files: dict[str, str],
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    located_raw = {location.raw for location in locations}
    for location in locations:
        relative = resolve_planned_relative_path(location.file_path, planned_files)
        grouped.setdefault(relative, []).append(location.raw)
    for raw in errors:
        if raw not in located_raw:
            grouped.setdefault("*", []).append(raw)
    return grouped


def dedupe_analyze_errors(errors: list[str]) -> list[str]:
    """Return analyzer diagnostics with duplicates removed (stable order)."""
    seen: set[str] = set()
    unique: list[str] = []
    for raw in errors:
        stripped = raw.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        unique.append(stripped)
    return unique

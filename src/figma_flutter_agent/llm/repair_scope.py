"""Map analyzer errors to scoped repair targets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.generator.layout_common import to_snake_case
from figma_flutter_agent.generator.paths import Architecture, screen_file_path
from figma_flutter_agent.schemas import ExtractedWidget, FlutterGenerationResponse

_ANALYZE_ERROR_LOCATION = re.compile(
    r"error\s+-\s+(?P<file>[^\s:]+\.dart):(?P<line>\d+):(?P<col>\d+)\s+-\s+(?P<message>.+)"
)
_FORMAT_ERROR_LOCATION = re.compile(
    r"^line (?P<line>\d+), column (?P<col>\d+) of (?P<file>.+\.dart): (?P<message>.+)$"
)


@dataclass(frozen=True)
class AnalyzeErrorLocation:
    """One analyzer diagnostic tied to a planned Dart file."""

    file_path: str
    line: int
    column: int
    message: str
    raw: str


@dataclass(frozen=True)
class RepairTarget:
    """One generation target included in a scoped repair request."""

    target: str
    widget_name: str | None
    code: str
    planned_path: str
    errors: tuple[str, ...]
    planned_excerpt: str


@dataclass(frozen=True)
class RepairScope:
    """Scoped repair context derived from analyzer output."""

    targets: tuple[RepairTarget, ...]
    unchanged_widget_names: tuple[str, ...] = ()
    screen_included: bool = False


def parse_analyze_error_locations(errors: list[str]) -> list[AnalyzeErrorLocation]:
    """Parse ``dart analyze`` error lines into file/line locations."""
    locations: list[AnalyzeErrorLocation] = []
    for raw in errors:
        stripped = raw.strip()
        match = _ANALYZE_ERROR_LOCATION.search(stripped)
        if match is None:
            match = _FORMAT_ERROR_LOCATION.match(stripped)
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


def _extract_planned_excerpt(source: str, line: int, *, context_lines: int = 25) -> str:
    lines = source.splitlines()
    if not lines:
        return ""
    index = max(0, min(line - 1, len(lines) - 1))
    start = max(0, index - context_lines)
    end = min(len(lines), index + context_lines + 1)
    numbered = [f"{number + 1:4}| {lines[number]}" for number in range(start, end)]
    return "\n".join(numbered)


def _widget_stem(widget: ExtractedWidget) -> str:
    return to_snake_case(widget.widget_name)


def _find_widget_by_planned_path(
    generation: FlutterGenerationResponse,
    planned_path: str,
) -> ExtractedWidget | None:
    stem = Path(planned_path).stem
    for widget in generation.extracted_widgets:
        widget_stem = _widget_stem(widget)
        if widget_stem == stem or f"{widget_stem}_widget" == stem:
            return widget
    return None


def _planned_path_keys(planned_files: dict[str, str]) -> dict[str, str]:
    """Map normalized planned paths (forward slashes) to the dict key form."""
    return {key.replace("\\", "/"): key for key in planned_files}


def resolve_planned_relative_path(file_path: str, planned_files: dict[str, str]) -> str:
    """Map analyzer or formatter paths to a key in ``planned_files``.

    Temp analyze projects report absolute Windows paths such as
    ``c:/Users/.../analyze_check/lib/widgets/group_widget.dart``. Repair scope
    must resolve those to ``lib/widgets/group_widget.dart``.
    """
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


def _group_errors_by_file(
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


def build_repair_scope(
    *,
    feature_name: str,
    planned_files: dict[str, str],
    current_generation: FlutterGenerationResponse,
    analyze_errors: list[str],
    architecture: Architecture = "feature_first",
    context_lines: int = 25,
) -> RepairScope:
    """Build scoped repair targets from analyzer errors and planned Dart files."""
    locations = parse_analyze_error_locations(analyze_errors)
    grouped = _group_errors_by_file(
        analyze_errors,
        locations,
        planned_files=planned_files,
    )
    screen_path = screen_file_path(feature_name, architecture=architecture)
    screen_normalized = screen_path.replace("\\", "/")

    affected_paths: set[str] = set()
    for location in locations:
        affected_paths.add(
            resolve_planned_relative_path(location.file_path, planned_files)
        )
    if not affected_paths and grouped.get("*"):
        affected_paths.add(screen_path)

    targets: list[RepairTarget] = []
    screen_included = False

    if screen_normalized in affected_paths:
        screen_errors = tuple(grouped.get(screen_normalized, []))
        planned_source = planned_files.get(screen_path, planned_files.get(screen_normalized, ""))
        excerpt_line = locations[0].line if locations else 1
        for location in locations:
            if resolve_planned_relative_path(location.file_path, planned_files) == screen_normalized:
                excerpt_line = location.line
                break
        targets.append(
            RepairTarget(
                target="screenCode",
                widget_name=None,
                code=current_generation.screen_code,
                planned_path=screen_path,
                errors=screen_errors or tuple(analyze_errors),
                planned_excerpt=_extract_planned_excerpt(
                    planned_source,
                    excerpt_line,
                    context_lines=context_lines,
                ),
            )
        )
        screen_included = True

    planned_keys = _planned_path_keys(planned_files)
    for normalized in sorted(affected_paths):
        if not normalized.startswith("lib/widgets/"):
            continue
        widget = _find_widget_by_planned_path(current_generation, normalized)
        if widget is None:
            continue
        file_errors = tuple(grouped.get(normalized, []))
        excerpt_line = 1
        for location in locations:
            if resolve_planned_relative_path(location.file_path, planned_files) == normalized:
                excerpt_line = location.line
                break
        planned_key = planned_keys.get(normalized, normalized)
        targets.append(
            RepairTarget(
                target="extractedWidget",
                widget_name=widget.widget_name,
                code=widget.code,
                planned_path=normalized,
                errors=file_errors or tuple(analyze_errors),
                planned_excerpt=_extract_planned_excerpt(
                    planned_files.get(planned_key, ""),
                    excerpt_line,
                    context_lines=context_lines,
                ),
            )
        )

    if not targets:
        excerpt_line = locations[0].line if locations else 1
        targets.append(
            RepairTarget(
                target="screenCode",
                widget_name=None,
                code=current_generation.screen_code,
                planned_path=screen_path,
                errors=tuple(analyze_errors),
                planned_excerpt=_extract_planned_excerpt(
                    planned_files.get(screen_path, ""),
                    excerpt_line,
                    context_lines=context_lines,
                ),
            )
        )
        screen_included = True

    included_widget_names = {
        target.widget_name for target in targets if target.widget_name is not None
    }
    unchanged = tuple(
        sorted(
            widget.widget_name
            for widget in current_generation.extracted_widgets
            if widget.widget_name not in included_widget_names
        )
    )
    return RepairScope(
        targets=tuple(targets),
        unchanged_widget_names=unchanged,
        screen_included=screen_included,
    )

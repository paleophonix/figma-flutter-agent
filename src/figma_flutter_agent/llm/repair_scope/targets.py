"""Repair target selection."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.layout.common import to_snake_case
from figma_flutter_agent.generator.paths import Architecture, screen_file_path
from figma_flutter_agent.llm.line_numbered_source import (
    format_line_numbered_source,
    format_numbered_excerpt,
)
from figma_flutter_agent.llm.repair_scope.locations import (
    group_errors_by_file,
    parse_analyze_error_locations,
    resolve_planned_relative_path,
)
from figma_flutter_agent.llm.repair_scope.models import RepairScope, RepairTarget
from figma_flutter_agent.schemas import ExtractedWidget, FlutterGenerationResponse


def extract_planned_excerpt(source: str, line: int, *, context_lines: int = 5) -> str:
    return format_numbered_excerpt(source, line, context_lines=context_lines)


def widget_stem(widget: ExtractedWidget) -> str:
    return to_snake_case(widget.widget_name)


def find_widget_by_planned_path(
    generation: FlutterGenerationResponse,
    planned_path: str,
) -> ExtractedWidget | None:
    stem = Path(planned_path).stem
    for widget in generation.extracted_widgets:
        current = widget_stem(widget)
        if current == stem or f"{current}_widget" == stem:
            return widget
    return None


def planned_path_keys(planned_files: dict[str, str]) -> dict[str, str]:
    """Map normalized planned paths (forward slashes) to the dict key form."""
    return {key.replace("\\", "/"): key for key in planned_files}


def append_screen_repair_target(
    targets: list[RepairTarget],
    *,
    use_screen_ir: bool,
    current_generation: FlutterGenerationResponse,
    screen_path: str,
    screen_errors: tuple[str, ...],
    planned_excerpt: str,
) -> None:
    if use_screen_ir and current_generation.screen_ir is not None:
        targets.append(
            RepairTarget(
                target="screenIr",
                widget_name=None,
                code=current_generation.screen_ir.model_dump_json(by_alias=True),
                planned_path=screen_path,
                errors=screen_errors,
                planned_excerpt=planned_excerpt,
            )
        )
        return
    targets.append(
        RepairTarget(
            target="screenCode",
            widget_name=None,
            code=current_generation.screen_code,
            planned_path=screen_path,
            errors=screen_errors,
            planned_excerpt=planned_excerpt,
        )
    )


def build_repair_scope(
    *,
    feature_name: str,
    planned_files: dict[str, str],
    current_generation: FlutterGenerationResponse,
    analyze_errors: list[str],
    architecture: Architecture = "feature_first",
    context_lines: int = 5,
    escalation_level: int = 1,
    use_screen_ir: bool = False,
) -> RepairScope:
    """Build scoped repair targets from analyzer errors and planned Dart files."""
    locations = parse_analyze_error_locations(analyze_errors)
    grouped = group_errors_by_file(analyze_errors, locations, planned_files=planned_files)
    screen_path = screen_file_path(feature_name, architecture=architecture)
    screen_normalized = screen_path.replace("\\", "/")

    affected_paths: set[str] = set()
    for location in locations:
        affected_paths.add(resolve_planned_relative_path(location.file_path, planned_files))
    if not affected_paths and grouped.get("*"):
        affected_paths.add(screen_path)

    if escalation_level >= 2:
        for planned_path in planned_files:
            normalized = planned_path.replace("\\", "/")
            if normalized.startswith("lib/widgets/"):
                affected_paths.add(normalized)

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
        append_screen_repair_target(
            targets,
            use_screen_ir=use_screen_ir,
            current_generation=current_generation,
            screen_path=screen_path,
            screen_errors=screen_errors or tuple(analyze_errors),
            planned_excerpt=(
                format_line_numbered_source(planned_source)
                if planned_source
                else extract_planned_excerpt(
                    planned_source,
                    excerpt_line,
                    context_lines=context_lines,
                )
            ),
        )
        screen_included = True

    keys = planned_path_keys(planned_files)
    for normalized in sorted(affected_paths):
        if not normalized.startswith("lib/widgets/"):
            continue
        widget = find_widget_by_planned_path(current_generation, normalized)
        if widget is None:
            continue
        file_errors = tuple(grouped.get(normalized, []))
        excerpt_line = 1
        for location in locations:
            if resolve_planned_relative_path(location.file_path, planned_files) == normalized:
                excerpt_line = location.line
                break
        planned_key = keys.get(normalized, normalized)
        widget_planned_source = planned_files.get(planned_key, "")
        targets.append(
            RepairTarget(
                target="extractedWidget",
                widget_name=widget.widget_name,
                code=widget.resolved_code(),
                planned_path=normalized,
                errors=file_errors or tuple(analyze_errors),
                planned_excerpt=(
                    format_line_numbered_source(widget_planned_source)
                    if widget_planned_source
                    else extract_planned_excerpt(
                        widget_planned_source,
                        excerpt_line,
                        context_lines=context_lines,
                    )
                ),
            )
        )

    if not targets:
        excerpt_line = locations[0].line if locations else 1
        append_screen_repair_target(
            targets,
            use_screen_ir=use_screen_ir,
            current_generation=current_generation,
            screen_path=screen_path,
            screen_errors=tuple(analyze_errors),
            planned_excerpt=extract_planned_excerpt(
                planned_files.get(screen_path, ""),
                excerpt_line,
                context_lines=context_lines,
            ),
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


def select_primary_repair_target(scope: RepairScope) -> RepairTarget:
    """Pick the target whose numbered source drives the repair environment."""
    for preferred in ("screenIr", "screenCode"):
        for target in scope.targets:
            if target.target == preferred:
                return target
    return scope.targets[0]

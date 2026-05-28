"""Map analyzer errors to scoped repair targets and APR prompt environment."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.generator.layout_common import to_snake_case
from figma_flutter_agent.llm.payload_slim import dump_clean_tree_for_llm
from figma_flutter_agent.generator.paths import Architecture, screen_file_path
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ExtractedWidget,
    FlutterGenerationResponse,
)
from figma_flutter_agent.llm.line_numbered_source import (
    format_line_numbered_source,
    format_numbered_excerpt,
)
from figma_flutter_agent.validation.figma_keys import parse_figma_key_ids

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


@dataclass(frozen=True)
class RepairEnvironmentContext:
    """Placeholder values for the repair system prompt ``<L6:ENVIRONMENT>`` block."""

    analyze_errors: str
    code: str
    semantic_hint: str
    failed_attempts_history: str
    unchanged_widget_names: str
    cpi_supervisor_directive: str = "(none)"


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


def _extract_planned_excerpt(source: str, line: int, *, context_lines: int = 5) -> str:
    return format_numbered_excerpt(source, line, context_lines=context_lines)


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
    context_lines: int = 5,
    escalation_level: int = 1,
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
        targets.append(
            RepairTarget(
                target="screenCode",
                widget_name=None,
                code=current_generation.screen_code,
                planned_path=screen_path,
                errors=screen_errors or tuple(analyze_errors),
                planned_excerpt=(
                    format_line_numbered_source(planned_source)
                    if planned_source
                    else _extract_planned_excerpt(
                        planned_source,
                        excerpt_line,
                        context_lines=context_lines,
                    )
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
        widget_planned_source = planned_files.get(planned_key, "")
        targets.append(
            RepairTarget(
                target="extractedWidget",
                widget_name=widget.widget_name,
                code=widget.code,
                planned_path=normalized,
                errors=file_errors or tuple(analyze_errors),
                planned_excerpt=(
                    format_line_numbered_source(widget_planned_source)
                    if widget_planned_source
                    else _extract_planned_excerpt(
                        widget_planned_source,
                        excerpt_line,
                        context_lines=context_lines,
                    )
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


def select_primary_repair_target(scope: RepairScope) -> RepairTarget:
    """Pick the target whose numbered source drives ``<L6:ENVIRONMENT>``."""
    for target in scope.targets:
        if target.target == "screenCode":
            return target
    return scope.targets[0]


def _find_clean_tree_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_clean_tree_node(child, node_id)
        if found is not None:
            return found
    return None


def _figma_key_tokens_near_line(source: str, line: int, *, window: int = 15) -> list[str]:
    lines = source.splitlines()
    if not lines:
        return []
    center = max(0, min(line - 1, len(lines) - 1))
    start = max(0, center - window)
    end = min(len(lines), center + window + 1)
    window_source = "\n".join(lines[start:end])
    return parse_figma_key_ids(window_source)


def extract_semantic_hint(
    clean_tree: CleanDesignTreeNode | None,
    *,
    planned_source: str,
    locations: list[AnalyzeErrorLocation],
) -> str:
    """Build Figma structural metadata near the failure site, or ``null``."""
    if clean_tree is None:
        return "null"
    anchor_line = locations[0].line if locations else 1
    tokens = _figma_key_tokens_near_line(planned_source, anchor_line)
    if not tokens:
        tokens = parse_figma_key_ids(planned_source)[:5]
    if not tokens:
        return "null"
    nodes: list[dict[str, object]] = []
    for node_id in tokens:
        node = _find_clean_tree_node(clean_tree, node_id)
        if node is not None:
            nodes.append(dump_clean_tree_for_llm(node))
    if not nodes:
        return "null"
    return json.dumps(nodes, ensure_ascii=False, indent=2)


def format_failed_attempts_history(records: list[str]) -> str:
    """Serialize prior failed patch bodies for trajectory invariance.

    Uses JSON so Dart/quotes in patch bodies cannot break ``<L6:ENVIRONMENT>`` markup.
    """
    if not records:
        return "(no prior failed patches in this run)"
    return json.dumps(records, ensure_ascii=False, indent=2)


def format_analyze_errors_block(errors: list[str]) -> str:
    """Format deduplicated analyzer errors for the system prompt."""
    if not errors:
        return "(none)"
    return "\n".join(f"- {line}" for line in errors)


def format_focused_error_context(
    *,
    planned_files: dict[str, str],
    analyze_errors: list[str],
    context_lines: int = 5,
) -> str:
    """Build per-error numbered excerpts around the failing compiler line."""
    locations = parse_analyze_error_locations(analyze_errors)
    if not locations:
        return ""
    blocks: list[str] = []
    seen: set[tuple[str, int, str]] = set()
    for location in locations:
        relative = resolve_planned_relative_path(location.file_path, planned_files)
        key = (relative, location.line, location.message)
        if key in seen:
            continue
        seen.add(key)
        planned_key = relative.replace("\\", "/")
        source = planned_files.get(planned_key, planned_files.get(relative, ""))
        if not source:
            continue
        line_start = max(1, location.line - context_lines)
        line_end = location.line + context_lines
        excerpt = _extract_planned_excerpt(
            source,
            location.line,
            context_lines=context_lines,
        )
        blocks.append(
            f"> Ты сломал код на строке {location.line} ({relative}:{location.column}).\n"
            f"> Сообщение: {location.message}\n"
            f"> Исправь СТРОГО этот фрагмент (строки {line_start}–{line_end}):\n"
            f"{excerpt}"
        )
    return "\n\n".join(blocks)


def format_unchanged_widget_names_block(names: tuple[str, ...]) -> str:
    """Format immutable widget scope boundaries for the system prompt."""
    if not names:
        return "(none)"
    return json.dumps(list(names), ensure_ascii=False)


def build_repair_environment_context(
    *,
    scope: RepairScope,
    planned_files: dict[str, str],
    analyze_errors: list[str],
    clean_tree: CleanDesignTreeNode | None = None,
    failed_attempts_history: list[str] | None = None,
    cpi_supervisor_directive: str | None = None,
    escalation_level: int = 1,
) -> RepairEnvironmentContext:
    """Build ``string.Template`` substitution values for the repair system prompt."""
    primary = select_primary_repair_target(scope)
    planned_key = primary.planned_path.replace("\\", "/")
    planned_source = planned_files.get(planned_key, planned_files.get(primary.planned_path, ""))
    if not planned_source:
        planned_source = primary.code
    unique_errors = dedupe_analyze_errors(analyze_errors)
    locations = parse_analyze_error_locations(unique_errors)
    focused = format_focused_error_context(
        planned_files=planned_files,
        analyze_errors=unique_errors,
    )
    numbered_source = (
        format_line_numbered_source(planned_source)
        if planned_source
        else primary.planned_excerpt
    )
    error_block = format_analyze_errors_block(unique_errors)
    if focused:
        error_block = f"{focused}\n\n--- all analyzer errors ---\n{error_block}"
    return RepairEnvironmentContext(
        analyze_errors=error_block,
        code=numbered_source,
        semantic_hint=extract_semantic_hint(
            clean_tree,
            planned_source=planned_source,
            locations=locations,
        ),
        failed_attempts_history=format_failed_attempts_history(failed_attempts_history or []),
        unchanged_widget_names=format_unchanged_widget_names_block(scope.unchanged_widget_names),
        cpi_supervisor_directive=cpi_supervisor_directive or "(none)",
    )


def format_repair_attempt_record(
    *,
    attempt: int,
    patch_codes: list[tuple[str, str | None, str]],
) -> str:
    """Format one failed repair turn for ``failedAttemptsHistory``.

    Args:
        attempt: One-based repair attempt index.
        patch_codes: ``(target, widget_name, code)`` tuples from the failed patch response.
    """
    lines = [f"Attempt {attempt} (failed):"]
    for target, widget_name, code in patch_codes:
        label = f"{target}"
        if widget_name:
            label = f"{label}({widget_name})"
        lines.append(f"--- {label} ---")
        lines.append(code)
    return "\n".join(lines)

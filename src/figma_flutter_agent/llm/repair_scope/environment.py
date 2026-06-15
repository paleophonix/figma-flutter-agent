"""Repair prompt environment formatting."""

from __future__ import annotations

import json

from figma_flutter_agent.llm.line_numbered_source import format_line_numbered_source
from figma_flutter_agent.llm.repair_scope.locations import (
    dedupe_analyze_errors,
    parse_analyze_error_locations,
    resolve_planned_relative_path,
)
from figma_flutter_agent.llm.repair_scope.models import RepairEnvironmentContext, RepairScope
from figma_flutter_agent.llm.repair_scope.semantic import extract_semantic_hint
from figma_flutter_agent.llm.repair_scope.targets import (
    extract_planned_excerpt,
    select_primary_repair_target,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode


def format_failed_attempts_history(records: list[str]) -> str:
    """Serialize prior failed patch bodies for trajectory invariance."""
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
        excerpt = extract_planned_excerpt(
            source,
            location.line,
            context_lines=context_lines,
        )
        blocks.append(
            f"> Ты сломал код на строке {location.line} ({relative}:{location.column}).\n"
            f"> Сообщение: {location.message}\n"
            f"> Исправь СТРОГО этот фрагмент (строки {line_start}-{line_end}):\n"
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
    """Build template substitution values for the repair system prompt."""
    del escalation_level
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
        format_line_numbered_source(planned_source) if planned_source else primary.planned_excerpt
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
    patch_codes: list[tuple[str, str | None, str | None]],
) -> str:
    """Format one failed repair turn for ``failedAttemptsHistory``."""
    lines = [f"Attempt {attempt} (failed):"]
    for target, widget_name, code in patch_codes:
        label = f"{target}"
        if widget_name:
            label = f"{label}({widget_name})"
        lines.append(f"--- {label} ---")
        lines.append(code if code is not None else "(no patch body)")
    return "\n".join(lines)

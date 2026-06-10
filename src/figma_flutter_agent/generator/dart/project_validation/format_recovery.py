"""On-disk recovery for ``dart format`` parse failures in generated projects."""

from __future__ import annotations

from pathlib import Path

from .analyze import ProjectAnalyzeResult
from .errors import collect_analyze_error_lines, parse_format_failed_paths
from .format import _run_dart_format_targets
from .format_limits import _DART_FORMAT_RECOVERY_PASSES
from .toolchain import _read_package_name


def _recover_project_format_failures(
    project_dir: Path,
    *,
    format_failure: ProjectAnalyzeResult,
    dart: str,
    format_target: list[str],
) -> ProjectAnalyzeResult | None:
    """Rewrite unparseable generated files on disk after deterministic repair."""
    from figma_flutter_agent.generator.planned.reconcile import (
        fallback_unparseable_screens_to_layout,
        repair_planned_format_parse_failures,
        sanitize_screen_emit_syntax,
    )

    format_paths = parse_format_failed_paths(format_failure.analyze_output)
    if not format_paths:
        return None
    package_name = _read_package_name(project_dir)
    planned: dict[str, str] = {}
    for path in format_paths:
        normalized = path.replace("\\", "/")
        file_path = project_dir / normalized
        if file_path.is_file():
            planned[normalized] = file_path.read_text(encoding="utf-8")
    if not planned:
        return None

    for path, content in list(planned.items()):
        if path.endswith("_screen.dart"):
            sanitized = sanitize_screen_emit_syntax(content)
            if sanitized != content:
                planned[path] = sanitized

    errors = collect_analyze_error_lines(
        format_failure.analyze_output,
        detail=format_failure.detail,
    )
    retry_targets = [
        str(project_dir / path.replace("\\", "/"))
        for path in format_paths
        if (project_dir / path.replace("\\", "/")).is_file()
    ]
    if not retry_targets:
        retry_targets = list(format_target)

    for repair_pass in range(_DART_FORMAT_RECOVERY_PASSES):
        repair_planned_format_parse_failures(
            planned,
            format_paths,
            analyze_errors=errors,
            repair_pass=repair_pass,
        )
        for path, content in planned.items():
            (project_dir / path).write_text(content, encoding="utf-8", newline="\n")
        retry = _run_dart_format_targets(
            project_dir,
            dart=dart,
            format_target=retry_targets,
        )
        if retry is None:
            return ProjectAnalyzeResult(
                passed=True,
                detail="dart format recovered after on-disk repair",
            )
        errors = collect_analyze_error_lines(
            retry.analyze_output,
            detail=retry.detail,
        )
        format_paths = parse_format_failed_paths(retry.analyze_output)

    fallback_unparseable_screens_to_layout(
        planned,
        format_paths,
        package_name=package_name,
    )
    for path, content in planned.items():
        (project_dir / path).write_text(content, encoding="utf-8", newline="\n")
    retry = _run_dart_format_targets(
        project_dir,
        dart=dart,
        format_target=retry_targets,
    )
    if retry is None:
        return ProjectAnalyzeResult(
            passed=True,
            detail="dart format recovered via layout delegate fallback",
        )
    return None

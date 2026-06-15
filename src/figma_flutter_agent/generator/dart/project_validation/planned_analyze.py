"""Full ``dart analyze`` flow over planned Dart files (widgets-first + reconcile)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from figma_flutter_agent.generator.writing.core import DartWriter

from .analyze import PlannedAnalyzeWorkspace, _validate_dart_project_inner
from .errors import collect_analyze_error_lines, parse_format_failed_paths
from .planned import PlannedAnalyzeOutcome, _filter_errors_for_paths, _widget_planned_paths
from .toolchain import (
    _toolchain_executables,
    _validate_package_imports,
    align_skeleton_pubspec_package_name,
)

if TYPE_CHECKING:
    from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens


def analyze_planned_dart_files(
    planned: dict[str, str],
    *,
    package_name: str = "demo_app",
    require_dart_sdk: bool = False,
    analyze_scope: str = "generated_only",
    analyze_stage: str | None = None,
    analyze_attempt: int | None = None,
    flutter_sdk: str | Path | None = None,
    widgets_first: bool = False,
    typography_tokens: DesignTokens | None = None,
    clean_tree: CleanDesignTreeNode | None = None,
    workspace: PlannedAnalyzeWorkspace | None = None,
    skip_planned_reconcile: bool = False,
    skip_dart_format: bool = False,
    widget_suffix: str | None = None,
    uses_svg: bool | None = None,
    cluster_summary: dict[str, int] | None = None,
    cluster_min_count: int = 2,
    destination_trees: dict[str, CleanDesignTreeNode] | None = None,
    use_package_imports: bool = True,
) -> PlannedAnalyzeOutcome:
    """Write planned files into a skeleton app and run dart/flutter analyze.

    Args:
        planned: Relative project paths mapped to generated Dart sources.
        package_name: Expected ``package:<name>/`` import prefix for planned Dart files.
        require_dart_sdk: When True, treat missing ``dart`` as a failure.
        analyze_scope: Passed to ``validate_dart_project`` (default: generated files only).
        analyze_stage: Stage slug for Dart error session logs when analyze fails.
        analyze_attempt: Optional one-based attempt index for repair/refine loops.
        flutter_sdk: Optional Flutter SDK root (``FIGMA_FLUTTER_SDK``) when not on PATH.
        workspace: Reuse one temp skeleton tree across repair attempts (avoids repeated pub get).
        skip_planned_reconcile: When True, skip ``reconcile_planned_dart_files`` (caller already ran it).

    Returns:
        Structured analyze outcome including parsed error lines when analyze fails.
    """
    from figma_flutter_agent.fixtures.screens_manifest import fixtures_root
    from figma_flutter_agent.generator.planned.reconcile import (
        reconcile_planned_dart_files,
        refresh_shrunk_and_delegate_planned_widgets,
    )

    flutter_skeleton = fixtures_root() / "flutter_skeleton"

    def _fail(
        detail: str,
        *,
        errors: tuple[str, ...],
        analyze_output: str = "",
        format_failed_paths: tuple[str, ...] = (),
    ) -> PlannedAnalyzeOutcome:
        from figma_flutter_agent.dart_error_log import record_dart_analyze_failure

        extra: dict[str, object] = {"analyzeScope": analyze_scope}
        if format_failed_paths:
            extra["formatFailedPaths"] = list(format_failed_paths)
        if analyze_stage is not None:
            record_dart_analyze_failure(
                stage=analyze_stage,
                detail=detail,
                errors=errors,
                analyze_output=analyze_output,
                attempt=analyze_attempt,
                extra=extra,
            )
        return PlannedAnalyzeOutcome(
            skipped=False,
            passed=False,
            detail=detail,
            errors=errors,
            analyze_output=analyze_output,
            format_failed_paths=format_failed_paths,
        )

    dart, flutter = _toolchain_executables(flutter_sdk)
    if dart is None:
        if require_dart_sdk:
            return _fail(
                "dart not found (PATH/FIGMA_FLUTTER_SDK)",
                errors=("dart not found (PATH/FIGMA_FLUTTER_SDK)",),
            )
        return PlannedAnalyzeOutcome(
            skipped=True,
            passed=True,
            detail="dart analyze skipped (no SDK)",
        )

    if not flutter_skeleton.is_dir():
        detail = f"flutter skeleton missing at {flutter_skeleton}"
        return _fail(detail, errors=(detail,))

    import_error = _validate_package_imports(planned, package_name)
    if import_error is not None:
        return _fail(import_error, errors=(import_error,))

    if not skip_planned_reconcile:
        planned = reconcile_planned_dart_files(
            planned,
            typography_tokens=typography_tokens,
            package_name=package_name,
            clean_tree=clean_tree,
        )
    elif skip_planned_reconcile:
        from figma_flutter_agent.generator.planned.reconcile import (
            consolidate_planned_widget_paths,
            repair_foreign_delegate_widget_builds,
            repair_self_referential_widget_builds,
            repair_stale_widget_ctor_names_in_planned,
            sync_widget_consumer_imports,
        )

        planned = repair_self_referential_widget_builds(planned)
        planned = repair_foreign_delegate_widget_builds(planned)
        planned = repair_stale_widget_ctor_names_in_planned(planned)
        if clean_tree is not None and widget_suffix and uses_svg is not None:
            planned = refresh_shrunk_and_delegate_planned_widgets(
                planned,
                clean_tree=clean_tree,
                widget_suffix=widget_suffix,
                uses_svg=uses_svg,
                package_name=package_name,
                use_package_imports=use_package_imports,
                cluster_summary=cluster_summary,
                cluster_min_count=cluster_min_count,
                destination_trees=destination_trees,
            )
            planned = consolidate_planned_widget_paths(planned)
            planned = repair_foreign_delegate_widget_builds(planned)
        planned = sync_widget_consumer_imports(planned, skip_consolidate=True)

    from figma_flutter_agent.generator.planned.reconcile import (
        ensure_planned_widget_import_closure,
        ensure_planned_widget_manifest,
    )

    ensure_planned_widget_manifest(planned)
    ensure_planned_widget_import_closure(planned)

    skip_pub_get = False
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if workspace is not None:
        project_dir = workspace.project_dir
        pub_failure = workspace.ensure_dependencies(flutter)
        if pub_failure is not None:
            errors = collect_analyze_error_lines(
                pub_failure.analyze_output,
                detail=pub_failure.detail,
            )
            return _fail(
                pub_failure.detail,
                errors=errors,
                analyze_output=pub_failure.analyze_output,
            )
        skip_pub_get = True
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="figma-flutter-spec23-")
        project_dir = Path(temp_dir.name) / "analyze_check"
        shutil.copytree(flutter_skeleton, project_dir)
        align_skeleton_pubspec_package_name(project_dir, package_name)

    try:
        writer = DartWriter(project_dir, enable_backup=False)
        writer.write_files(planned)
        all_paths = sorted(key.replace("\\", "/") for key in planned)
        widget_paths = _widget_planned_paths(planned)

        if widgets_first and widget_paths:
            widget_outcome = _validate_dart_project_inner(
                project_dir,
                analyze_scope=analyze_scope,
                relative_paths=list(widget_paths),
                dart=dart,
                flutter=flutter,
                flutter_sdk=flutter_sdk,
                skip_pub_get=skip_pub_get,
                skip_dart_format=skip_dart_format,
            )
            if not widget_outcome.passed:
                errors = collect_analyze_error_lines(
                    widget_outcome.analyze_output,
                    detail=widget_outcome.detail,
                )
                errors = _filter_errors_for_paths(errors, widget_paths)
                format_paths: tuple[str, ...] = ()
                if "dart format failed" in widget_outcome.detail.lower():
                    format_paths = parse_format_failed_paths(widget_outcome.analyze_output)
                    format_paths = (
                        tuple(path for path in format_paths if path in widget_paths) or format_paths
                    )
                detail = (
                    "widgets-first gate: lib/widgets/ must analyze clean before screen "
                    f"({widget_outcome.detail})"
                )
                return _fail(
                    detail,
                    errors=errors,
                    analyze_output=widget_outcome.analyze_output,
                    format_failed_paths=format_paths,
                )

        outcome = _validate_dart_project_inner(
            project_dir,
            analyze_scope=analyze_scope,
            relative_paths=all_paths,
            dart=dart,
            flutter=flutter,
            flutter_sdk=flutter_sdk,
            skip_pub_get=skip_pub_get,
            skip_dart_format=skip_dart_format,
        )
        if outcome.passed:
            return PlannedAnalyzeOutcome(
                skipped=False,
                passed=True,
                detail=outcome.detail,
            )
        errors = collect_analyze_error_lines(outcome.analyze_output, detail=outcome.detail)
        format_paths = ()
        if "dart format failed" in outcome.detail.lower():
            format_paths = parse_format_failed_paths(outcome.analyze_output)
        return _fail(
            outcome.detail,
            errors=errors,
            analyze_output=outcome.analyze_output,
            format_failed_paths=format_paths,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def validate_planned_dart_files(
    planned: dict[str, str],
    *,
    package_name: str = "demo_app",
    require_dart_sdk: bool = False,
    analyze_scope: str = "generated_only",
) -> tuple[bool, str]:
    """Write planned files into a skeleton app and run dart/flutter analyze.

    Args:
        planned: Relative project paths mapped to generated Dart sources.
        package_name: Expected ``package:<name>/`` import prefix for planned Dart files.
        require_dart_sdk: When True, fail when ``dart`` is not on ``PATH``.
        analyze_scope: Passed to ``validate_dart_project`` (default: generated files only).

    Returns:
        Tuple of success flag and detail message for acceptance reporting.
    """
    outcome = analyze_planned_dart_files(
        planned,
        package_name=package_name,
        require_dart_sdk=require_dart_sdk,
        analyze_scope=analyze_scope,
    )
    if outcome.skipped:
        return True, outcome.detail
    return outcome.passed, outcome.detail

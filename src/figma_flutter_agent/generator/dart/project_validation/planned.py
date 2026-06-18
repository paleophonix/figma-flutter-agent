"""Planned Dart file analysis: parse gate, analyze gate, and widgets-first flow."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from figma_flutter_agent.generator.writing.core import DartWriter

from .errors import collect_analyze_error_lines, parse_format_failed_paths
from .format import _run_dart_format_targets
from .format_limits import _DART_FORMAT_RECOVERY_PASSES
from .toolchain import (
    _toolchain_executables,
    _validate_package_imports,
    align_skeleton_pubspec_package_name,
)

if TYPE_CHECKING:
    from figma_flutter_agent.generator.planned.reconcile.bootstrap_refresh import (
        PlannedBootstrapContext,
    )
    from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens


@dataclass(frozen=True)
class PlannedAnalyzeOutcome:
    """Result of analyzing planned Dart files in a temp skeleton project."""

    skipped: bool
    passed: bool
    detail: str
    errors: tuple[str, ...] = ()
    analyze_output: str = ""
    format_failed_paths: tuple[str, ...] = ()
    toolchain_timeout: bool = False


def _widget_planned_paths(planned: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            key.replace("\\", "/")
            for key in planned
            if key.replace("\\", "/").startswith("lib/widgets/") and key.endswith(".dart")
        )
    )


def _filter_errors_for_paths(
    errors: tuple[str, ...],
    allowed_paths: tuple[str, ...],
) -> tuple[str, ...]:
    if not allowed_paths:
        return errors
    allowed_names = {Path(path).name for path in allowed_paths}
    filtered: list[str] = []
    for error in errors:
        normalized = error.replace("\\", "/")
        if any(path in normalized for path in allowed_paths):
            filtered.append(error)
            continue
        if any(name in normalized for name in allowed_names):
            filtered.append(error)
    return tuple(filtered) if filtered else errors


def _planned_delimiter_error_messages(planned: dict[str, str]) -> list[str]:
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters
    from figma_flutter_agent.generator.planned.reconcile.paths import planned_content_for_path

    errors: list[str] = []
    seen_normalized: set[str] = set()
    for path in sorted(planned.keys()):
        if not path.endswith(".dart"):
            continue
        normalized = path.replace("\\", "/")
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        located = planned_content_for_path(planned, normalized)
        content = located[1] if located is not None else planned[path]
        delimiter_error = validate_dart_delimiters(content)
        if delimiter_error is not None:
            errors.append(f"{normalized}: {delimiter_error}")
    return errors


def _repair_or_fallback_planned_delimiter_errors(
    planned: dict[str, str],
    *,
    package_name: str,
) -> list[str]:
    """Repair delimiter issues in planned Dart; layout-fallback broken screens before failing."""
    from figma_flutter_agent.generator.dart.llm_codegen import repair_dart_delimiters
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        apply_planned_delimiter_balance,
        repair_planned_dart_delimiters_if_needed,
    )
    from figma_flutter_agent.generator.planned.reconcile import (
        fallback_unparseable_screens_to_layout,
        sanitize_screen_emit_syntax,
    )

    for _ in range(4):
        broken_paths = [
            path.split(":", 1)[0] for path in _planned_delimiter_error_messages(planned)
        ]
        if not broken_paths:
            return []
        for path in broken_paths:
            if not path.replace("\\", "/").endswith("_screen.dart"):
                continue
            content = planned.get(path, "")
            content = sanitize_screen_emit_syntax(content)
            content = repair_planned_dart_delimiters_if_needed(content)
            content = apply_planned_delimiter_balance(content, force=True)
            content = repair_dart_delimiters(content)
            planned[path] = content

    broken_paths = [path.split(":", 1)[0] for path in _planned_delimiter_error_messages(planned)]
    screen_broken = [
        path for path in broken_paths if path.replace("\\", "/").endswith("_screen.dart")
    ]
    if screen_broken:
        fallback_unparseable_screens_to_layout(
            planned,
            tuple(screen_broken),
            package_name=package_name,
        )
    return _planned_delimiter_error_messages(planned)


def gate_planned_dart_syntax(
    planned: dict[str, str],
    *,
    package_name: str = "demo_app",
    require_dart_sdk: bool = False,
    analyze_stage: str | None = "emit_parse_gate",
    flutter_sdk: str | Path | None = None,
    typography_tokens: DesignTokens | None = None,
    clean_tree: CleanDesignTreeNode | None = None,
    bootstrap_context: PlannedBootstrapContext | None = None,
) -> PlannedAnalyzeOutcome:
    """Fail-fast when planned Dart is not parseable (dart format only, temp tree).

    Writes ``planned`` into the flutter skeleton workspace and runs ``dart format``
    on each file. Does not run ``dart analyze`` вЂ” use :func:`analyze_planned_dart_files`
    for full spec23 gates.
    """
    from figma_flutter_agent.fixtures.screens_manifest import fixtures_root

    flutter_skeleton = fixtures_root() / "flutter_skeleton"

    if not planned:
        return PlannedAnalyzeOutcome(skipped=True, passed=True, detail="no planned dart files")

    from figma_flutter_agent.generator.planned.reconcile import canonicalize_planned_path_keys
    from figma_flutter_agent.generator.planned.reconcile.bootstrap_refresh import (
        ensure_compiler_bootstrap_planned_files,
        render_planned_bootstrap_files,
    )

    canonicalize_planned_path_keys(planned)

    if bootstrap_context is not None:
        bootstrap_files = render_planned_bootstrap_files(bootstrap_context)
        refreshed = ensure_compiler_bootstrap_planned_files(
            planned,
            bootstrap_files=bootstrap_files,
            force=True,
        )
        planned.clear()
        planned.update(refreshed)
        canonicalize_planned_path_keys(planned)

    if typography_tokens is not None:
        from figma_flutter_agent.generator.renderer import DartRenderer
        from figma_flutter_agent.generator.renderer_theme import ensure_theme_typography_coherence

        renderer = DartRenderer()
        ensure_theme_typography_coherence(
            planned,
            typography_tokens,
            renderer._env,
        )

    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        repair_planned_dart_delimiters_if_needed,
    )

    for path in list(planned.keys()):
        if not path.endswith("_screen.dart"):
            continue
        content = planned[path]
        if validate_dart_delimiters(content) is None:
            continue
        repaired = repair_planned_dart_delimiters_if_needed(content)
        if repaired != content:
            planned[path] = repaired

    def _fail(
        detail: str,
        *,
        errors: tuple[str, ...],
        analyze_output: str = "",
        format_failed_paths: tuple[str, ...] = (),
    ) -> PlannedAnalyzeOutcome:
        from figma_flutter_agent.dart_error_log import record_dart_analyze_failure

        extra: dict[str, object] = {"analyzeScope": "emit_parse_gate"}
        if format_failed_paths:
            extra["formatFailedPaths"] = list(format_failed_paths)
        if analyze_stage is not None:
            record_dart_analyze_failure(
                stage=analyze_stage,
                detail=detail,
                errors=errors,
                analyze_output=analyze_output,
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

    dart, _flutter = _toolchain_executables(flutter_sdk)
    if dart is None:
        if require_dart_sdk:
            return _fail(
                "dart not found (PATH/FIGMA_FLUTTER_SDK)",
                errors=("dart not found (PATH/FIGMA_FLUTTER_SDK)",),
            )
        return PlannedAnalyzeOutcome(
            skipped=True,
            passed=True,
            detail="emit parse gate skipped (no SDK)",
        )

    if not flutter_skeleton.is_dir():
        detail = f"flutter skeleton missing at {flutter_skeleton}"
        return _fail(detail, errors=(detail,))

    import_error = _validate_package_imports(planned, package_name)
    if import_error is not None:
        return _fail(import_error, errors=(import_error,))

    from figma_flutter_agent.generator.planned.reconcile import (
        force_polluted_feature_screens_to_layout,
        sanitize_screen_emit_syntax,
    )

    force_polluted_feature_screens_to_layout(
        planned,
        package_name=package_name,
        responsive_enabled=True,
    )
    for path, content in list(planned.items()):
        if path.endswith("_screen.dart"):
            sanitized = sanitize_screen_emit_syntax(content)
            if sanitized != content:
                planned[path] = sanitized

    delimiter_errors = _repair_or_fallback_planned_delimiter_errors(
        planned,
        package_name=package_name,
    )
    if delimiter_errors:
        return _fail(
            "emit parse gate: invalid Dart delimiters in planned output",
            errors=tuple(delimiter_errors),
        )

    with tempfile.TemporaryDirectory(prefix="figma-flutter-parse-gate-") as tmp:
        project_dir = Path(tmp) / "parse_gate"
        shutil.copytree(flutter_skeleton, project_dir)
        align_skeleton_pubspec_package_name(project_dir, package_name)
        from figma_flutter_agent.generator.planned.reconcile import (
            fallback_unparseable_screens_to_layout,
            repair_planned_format_parse_failures,
        )

        writer = DartWriter(project_dir, enable_backup=False)
        writer.write_files(planned)
        relative_paths = sorted(key.replace("\\", "/") for key in planned)
        dart_targets = [str(project_dir / path) for path in relative_paths]
        format_outcome: PlannedAnalyzeOutcome | None = None
        for repair_pass in range(_DART_FORMAT_RECOVERY_PASSES):
            format_outcome = _run_dart_format_targets(
                project_dir,
                dart=dart,
                format_target=dart_targets,
            )
            if format_outcome is None:
                break
            errors = collect_analyze_error_lines(
                format_outcome.analyze_output,
                detail=format_outcome.detail,
            )
            format_paths = parse_format_failed_paths(format_outcome.analyze_output)
            repair_planned_format_parse_failures(
                planned,
                format_paths,
                analyze_errors=errors,
                repair_pass=repair_pass,
            )
            writer.write_files(planned)
            dart_targets = [str(project_dir / path.replace("\\", "/")) for path in sorted(planned)]
        if format_outcome is not None:
            format_paths = parse_format_failed_paths(format_outcome.analyze_output)
            fallback_unparseable_screens_to_layout(
                planned,
                format_paths,
                package_name=package_name,
            )
            writer.write_files(planned)
            dart_targets = [str(project_dir / path.replace("\\", "/")) for path in sorted(planned)]
            format_outcome = _run_dart_format_targets(
                project_dir,
                dart=dart,
                format_target=dart_targets,
            )
        if format_outcome is None:
            return PlannedAnalyzeOutcome(
                skipped=False,
                passed=True,
                detail="emit parse gate passed",
            )
        errors = collect_analyze_error_lines(
            format_outcome.analyze_output,
            detail=format_outcome.detail,
        )
        format_paths = parse_format_failed_paths(format_outcome.analyze_output)
        return _fail(
            "emit parse gate: dart format could not parse planned output",
            errors=errors,
            analyze_output=format_outcome.analyze_output,
            format_failed_paths=format_paths,
        )

"""Dart/Flutter project analysis (dart analyze / flutter analyze)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from figma_flutter_agent.tools.process_run import (
    DART_ANALYZE_TIMEOUT_SEC,
    run_subprocess,
)

from .errors import collect_analyze_error_lines
from .toolchain import (
    _run_flutter_pub_get,
    _strip_windows_zone_identifier_noise,
    _toolchain_executables,
    align_skeleton_pubspec_package_name,
)

if TYPE_CHECKING:
    pass

_ANALYZE_ERROR_LINE = __import__("re").compile(r"^\s*error\s+-", __import__("re").MULTILINE)
_DART_ANALYZE_CHUNK_SIZE = 6
_DART_ANALYZE_CHUNK_TIMEOUT_RETRIES = 1


def is_dart_analyze_timeout_detail(detail: str) -> bool:
    """Return True when an analyze outcome is a subprocess timeout, not a compiler error."""
    normalized = detail.strip().lower()
    return "timed out after" in normalized and "dart analyze" in normalized


@dataclass(frozen=True)
class ProjectAnalyzeResult:
    """Outcome of format/analyze against a on-disk Flutter project."""

    passed: bool
    detail: str
    analyze_output: str = ""


def _analyze_failure_details(result: subprocess.CompletedProcess[str]) -> str:
    """Combine analyze stdout/stderr while hiding known Windows SDK wrapper noise."""
    stderr = _strip_windows_zone_identifier_noise(result.stderr)
    stdout = (result.stdout or "").strip()
    if stdout and stderr:
        return f"{stdout}\n{stderr}"
    return stdout or stderr or "dart analyze failed with no output"


def _analyze_has_errors(details: str) -> bool:
    """Return True when analyzer output contains error-level diagnostics."""
    return _ANALYZE_ERROR_LINE.search(details) is not None


def _timeout_analyze_result(label: str, timeout_sec: float) -> ProjectAnalyzeResult:
    detail = f"{label} timed out after {timeout_sec:.0f}s"
    logger.error(detail)
    return ProjectAnalyzeResult(passed=False, detail=detail, analyze_output=detail)


def _build_analyze_command(
    *,
    dart: str,
    flutter: str | None,
    scope_path_list: bool,
    dart_targets: list[Path],
    project_dir: Path,
) -> tuple[list[str], str]:
    """Build analyze CLI argv and a short tool label for logs."""
    if scope_path_list:
        target_args = [str(path) for path in dart_targets]
        return (
            [dart, "analyze", "--no-fatal-warnings", *target_args],
            "dart analyze (generated)",
        )
    if flutter is not None:
        return (
            [flutter, "analyze", "--no-fatal-warnings", str(project_dir)],
            "flutter analyze",
        )
    return (
        [dart, "analyze", "--no-fatal-warnings", str(project_dir)],
        "dart analyze",
    )


def _dart_analyze_timeout_sec(targets: list[Path]) -> float:
    """Scale analyze timeout with file count and size (large generated widgets need headroom)."""
    total_bytes = 0
    for path in targets:
        try:
            total_bytes += path.stat().st_size
        except OSError:
            continue
    return min(
        300.0,
        max(
            DART_ANALYZE_TIMEOUT_SEC,
            45.0 + len(targets) * 12.0 + total_bytes / 10_000.0,
        ),
    )


def _run_scoped_dart_analyze(
    project_dir: Path,
    *,
    dart: str,
    dart_targets: list[Path],
) -> ProjectAnalyzeResult:
    """Analyze explicit Dart paths in chunks (``dart analyze``; faster than ``flutter analyze`` on Windows)."""
    if not dart_targets:
        return ProjectAnalyzeResult(passed=True, detail="dart analyze skipped (no targets)")

    tool_name = "dart analyze (generated)"
    warning_details: list[str] = []
    chunks = [
        dart_targets[index : index + _DART_ANALYZE_CHUNK_SIZE]
        for index in range(0, len(dart_targets), _DART_ANALYZE_CHUNK_SIZE)
    ]
    from .minified_expand import prepare_project_dart_for_analyze

    prepare_project_dart_for_analyze(
        project_dir,
        [str(path.relative_to(project_dir)).replace("\\", "/") for path in dart_targets],
    )
    for chunk_index, chunk in enumerate(chunks, start=1):
        command, _ = _build_analyze_command(
            dart=dart,
            flutter=None,
            scope_path_list=True,
            dart_targets=chunk,
            project_dir=project_dir,
        )
        timeout = _dart_analyze_timeout_sec(chunk)
        label = f"{tool_name} ({chunk_index}/{len(chunks)})" if len(chunks) > 1 else tool_name
        analyze_result = None
        for retry_index in range(_DART_ANALYZE_CHUNK_TIMEOUT_RETRIES + 1):
            try:
                analyze_result = run_subprocess(
                    command,
                    cwd=project_dir,
                    label=label,
                    timeout_sec=timeout,
                )
                break
            except subprocess.TimeoutExpired:
                if retry_index < _DART_ANALYZE_CHUNK_TIMEOUT_RETRIES:
                    logger.warning(
                        "{} timed out after {:.0f}s; retrying chunk once",
                        label,
                        timeout,
                    )
                    continue
                return _timeout_analyze_result(label, timeout)
        assert analyze_result is not None
        if analyze_result.returncode != 0:
            details = _analyze_failure_details(analyze_result)
            if _analyze_has_errors(details):
                return ProjectAnalyzeResult(
                    passed=False,
                    detail=f"{tool_name} reported issues in generated project",
                    analyze_output=details,
                )
            warning_details.append(details)

    if warning_details:
        return ProjectAnalyzeResult(
            passed=True,
            detail=f"{tool_name} warnings only",
            analyze_output="\n".join(warning_details),
        )
    return ProjectAnalyzeResult(passed=True, detail=f"{tool_name} passed")


def _dart_paths(project_dir: Path, relative_paths: list[str]) -> list[Path]:
    """Resolve planned relative paths to existing Dart files under the project."""
    resolved: list[Path] = []
    for relative in relative_paths:
        if not relative.endswith(".dart"):
            continue
        candidate = project_dir / relative
        if candidate.is_file():
            resolved.append(candidate)
    return resolved


class PlannedAnalyzeWorkspace:
    """Reusable skeleton project for multiple ``analyze_planned_dart_files`` calls in one session."""

    def __init__(
        self,
        project_dir: Path,
        temp_dir: tempfile.TemporaryDirectory[str],
        *,
        package_name: str,
    ) -> None:
        self.project_dir = project_dir
        self._temp_dir = temp_dir
        self.package_name = package_name
        self._dependencies_ready = False

    @classmethod
    def create(cls, *, package_name: str) -> PlannedAnalyzeWorkspace:
        from figma_flutter_agent.fixtures.screens_manifest import fixtures_root

        flutter_skeleton = fixtures_root() / "flutter_skeleton"
        if not flutter_skeleton.is_dir():
            msg = f"flutter skeleton missing at {flutter_skeleton}"
            raise FileNotFoundError(msg)
        temp_dir = tempfile.TemporaryDirectory(prefix="figma-flutter-spec23-")
        project_dir = Path(temp_dir.name) / "analyze_check"
        shutil.copytree(flutter_skeleton, project_dir)
        align_skeleton_pubspec_package_name(project_dir, package_name)
        return cls(project_dir, temp_dir, package_name=package_name)

    def close(self) -> None:
        self._temp_dir.cleanup()

    def __enter__(self) -> PlannedAnalyzeWorkspace:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def ensure_dependencies(self, flutter: str | None) -> ProjectAnalyzeResult | None:
        """Resolve packages once per workspace (repair loops call analyze many times)."""
        if self._dependencies_ready:
            return None
        from figma_flutter_agent.generator.pub_get_policy import (
            log_pub_get_skip,
            needs_pub_get,
        )

        if not needs_pub_get(self.project_dir):
            log_pub_get_skip(self.project_dir)
            self._dependencies_ready = True
            return None
        failure = _run_flutter_pub_get(self.project_dir, flutter)
        if failure is None:
            from figma_flutter_agent.generator.pub_get_policy import mark_pubspec_resolved

            mark_pubspec_resolved(self.project_dir)
            self._dependencies_ready = True
        return failure


def _validate_dart_project_inner(
    project_dir: Path,
    *,
    analyze_scope: str = "project",
    relative_paths: list[str] | None = None,
    dart: str | None = None,
    flutter: str | None = None,
    flutter_sdk: str | Path | None = None,
    skip_dart_format: bool = False,
    skip_pub_get: bool = False,
) -> ProjectAnalyzeResult:
    """Run ``dart format`` and analyze; return structured outcome without raising."""
    from .format import _run_dart_format_targets
    from .format_recovery import _recover_project_format_failures

    if dart is None:
        dart, flutter = _toolchain_executables(flutter_sdk)
    elif flutter is None:
        _, flutter = _toolchain_executables(flutter_sdk)
    if dart is None:
        return ProjectAnalyzeResult(passed=True, detail="dart analyze skipped (no SDK)")

    scope_path_list = analyze_scope in ("generated_only", "all_planned", "written_only")
    dart_targets = _dart_paths(project_dir, relative_paths or []) if scope_path_list else []

    if scope_path_list and not dart_targets:
        return ProjectAnalyzeResult(passed=True, detail="dart analyze skipped (no targets)")

    if scope_path_list:
        format_target = [str(path) for path in dart_targets]
    else:
        format_target = []
        if analyze_scope == "project" and not skip_dart_format:
            logger.info(
                "Skipping dart format for project analyze scope (format generated files only)"
            )
    if format_target and not skip_dart_format:
        format_failure = _run_dart_format_targets(
            project_dir,
            dart=dart,
            format_target=format_target,
        )
        if format_failure is not None:
            recovered = _recover_project_format_failures(
                project_dir,
                format_failure=format_failure,
                dart=dart,
                format_target=format_target,
            )
            if recovered is not None:
                return recovered
            return format_failure
    elif format_target and skip_dart_format:
        logger.info("Skipping dart format for planned analyze (analyze-only gate)")

    if not skip_pub_get:
        pub_get_failure = _run_flutter_pub_get(project_dir, flutter)
        if pub_get_failure is not None:
            return pub_get_failure

    if scope_path_list:
        return _run_scoped_dart_analyze(
            project_dir,
            dart=dart,
            dart_targets=dart_targets,
        )

    analyze_command, tool_name = _build_analyze_command(
        dart=dart,
        flutter=flutter,
        scope_path_list=False,
        dart_targets=dart_targets,
        project_dir=project_dir,
    )
    try:
        analyze_result = run_subprocess(
            analyze_command,
            cwd=project_dir,
            label=tool_name,
            timeout_sec=DART_ANALYZE_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return _timeout_analyze_result(tool_name, DART_ANALYZE_TIMEOUT_SEC)
    if analyze_result.returncode != 0:
        details = _analyze_failure_details(analyze_result)
        if _analyze_has_errors(details):
            return ProjectAnalyzeResult(
                passed=False,
                detail=f"{tool_name} reported issues in generated project",
                analyze_output=details,
            )
        return ProjectAnalyzeResult(
            passed=True, detail=f"{tool_name} warnings only", analyze_output=details
        )

    return ProjectAnalyzeResult(passed=True, detail=f"{tool_name} passed")


def validate_dart_project(
    project_dir: Path,
    *,
    require_dart_sdk: bool = False,
    analyze_scope: str = "project",
    relative_paths: list[str] | None = None,
    analyze_stage: str = "write",
    analyze_attempt: int | None = None,
    flutter_sdk: str | Path | None = None,
) -> None:
    """Run ``dart format`` and ``dart``/``flutter analyze`` against the Flutter project.

    Args:
        project_dir: Flutter project root containing ``pubspec.yaml``.
        require_dart_sdk: When True, raise if ``dart`` is not on ``PATH``.
        analyze_scope: ``project`` (entire tree), ``all_planned`` / ``generated_only``
            (``relative_paths`` list), or ``written_only`` (subset passed by caller).
        relative_paths: Dart paths to analyze when using a path-list scope.
        analyze_stage: Stage slug for Dart error session logs.
        analyze_attempt: Optional one-based attempt index for repair/refine loops.
        flutter_sdk: Optional Flutter SDK root (``FIGMA_FLUTTER_SDK``) when not on PATH.

    Raises:
        GenerationError: If validation tools are required but missing, or checks fail.
    """
    from figma_flutter_agent.dart_error_log import record_dart_analyze_failure
    from figma_flutter_agent.errors import GenerationError

    dart, flutter = _toolchain_executables(flutter_sdk)
    if dart is None:
        if require_dart_sdk:
            raise GenerationError(
                "dart not found; set FIGMA_FLUTTER_SDK or validation.require_dart_sdk: false"
            )
        logger.warning(
            "dart not found (PATH/FIGMA_FLUTTER_SDK); skipping post-generation validation"
        )
        return

    outcome = _validate_dart_project_inner(
        project_dir,
        analyze_scope=analyze_scope,
        relative_paths=relative_paths,
        dart=dart,
        flutter=flutter,
    )
    if outcome.passed:
        logger.info("{} for {}", outcome.detail, project_dir)
        return

    errors = collect_analyze_error_lines(outcome.analyze_output, detail=outcome.detail)
    record_dart_analyze_failure(
        stage=analyze_stage,
        detail=outcome.detail,
        errors=errors,
        analyze_output=outcome.analyze_output,
        attempt=analyze_attempt,
        extra={"analyzeScope": analyze_scope},
    )
    if outcome.analyze_output:
        logger.error("{}: {}", outcome.detail, outcome.analyze_output)
    else:
        logger.error("{}", outcome.detail)
    raise GenerationError(outcome.detail)

"""Post-generation Dart validation."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.dart_error_log import record_dart_analyze_failure
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files
from figma_flutter_agent.generator.writer import DartWriter
from figma_flutter_agent.tools.process_run import (
    DART_ANALYZE_TIMEOUT_SEC,
    DART_FORMAT_TIMEOUT_SEC,
    FLUTTER_PUB_GET_TIMEOUT_SEC,
    run_subprocess,
)

_FLUTTER_SKELETON = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "flutter_skeleton"
_PACKAGE_IMPORT = re.compile(r"""import\s+['"]package:([^/'"]+)/""")
_WINDOWS_ZONE_IDENTIFIER_NOISE = re.compile(
    r"^Unblock-File:.*Zone\.Identifier['\"]?\.\s*$",
    re.MULTILINE,
)
_ANALYZE_ERROR_LINE = re.compile(r"^\s*error\s+-", re.MULTILINE)
_FORMAT_PARSE_ERROR_LINE = re.compile(
    r"^line \d+, column \d+ of .+?: .+$",
    re.MULTILINE,
)
_FORMAT_FAILED_PATH_RE = re.compile(
    r"line \d+, column \d+ of .*?(?P<path>lib[/\\][^\s:]+\.dart)",
    re.IGNORECASE,
)


def _toolchain_executables(
    flutter_sdk: str | Path | None = None,
) -> tuple[str | None, str | None]:
    """Resolve ``dart`` and ``flutter`` from PATH or ``FIGMA_FLUTTER_SDK``."""
    from figma_flutter_agent.dev.flutter_sdk import (
        resolve_dart_executable,
        resolve_flutter_executable,
    )

    dart = resolve_dart_executable(sdk_root=flutter_sdk)
    flutter = resolve_flutter_executable(sdk_root=flutter_sdk)
    return dart, flutter


def _resolve_dart_executable(flutter_sdk: str | Path | None = None) -> str | None:
    """Return a Dart CLI path (PATH or ``FIGMA_FLUTTER_SDK``)."""
    dart, _ = _toolchain_executables(flutter_sdk)
    return dart


def _strip_windows_zone_identifier_noise(text: str) -> str:
    """Remove Flutter SDK ``Unblock-File`` noise from captured CLI stderr."""
    cleaned = _WINDOWS_ZONE_IDENTIFIER_NOISE.sub("", text)
    return cleaned.strip()


def _analyze_failure_details(result: subprocess.CompletedProcess[str]) -> str:
    """Combine analyze stdout/stderr while hiding known Windows SDK wrapper noise."""
    stderr = _strip_windows_zone_identifier_noise(result.stderr)
    stdout = result.stdout.strip()
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


def _run_flutter_pub_get(
    project_dir: Path,
    flutter: str | None,
) -> ProjectAnalyzeResult | None:
    """Resolve packages in a Flutter project before analyze. Returns failure or None."""
    if flutter is None:
        return None
    pubspec = project_dir / "pubspec.yaml"
    if not pubspec.is_file():
        return None
    try:
        result = run_subprocess(
            [flutter, "pub", "get"],
            cwd=project_dir,
            label="flutter pub get",
            timeout_sec=FLUTTER_PUB_GET_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return _timeout_analyze_result("flutter pub get", FLUTTER_PUB_GET_TIMEOUT_SEC)
    if result.returncode != 0:
        details = _analyze_failure_details(result)
        return ProjectAnalyzeResult(
            passed=False,
            detail="flutter pub get failed before analyze",
            analyze_output=details,
        )
    return None


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
        if flutter is not None:
            return (
                [flutter, "analyze", "--no-fatal-warnings", *target_args],
                "flutter analyze (generated)",
            )
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


@dataclass(frozen=True)
class ProjectAnalyzeResult:
    """Outcome of format/analyze against a on-disk Flutter project."""

    passed: bool
    detail: str
    analyze_output: str = ""


def _run_dart_format_targets(
    project_dir: Path,
    *,
    dart: str,
    format_target: list[str],
    timeout_sec: float,
) -> ProjectAnalyzeResult | None:
    """Format Dart targets; use per-file runs when multiple paths to isolate hangs."""
    per_file_timeout = max(15.0, min(timeout_sec, timeout_sec / max(len(format_target), 1)))
    outputs: list[str] = []
    for index, target in enumerate(format_target):
        try:
            result = run_subprocess(
                [dart, "format", target],
                cwd=project_dir,
                label="dart format",
                timeout_sec=per_file_timeout,
            )
        except subprocess.TimeoutExpired:
            return _timeout_analyze_result(
                f"dart format ({target})",
                int(per_file_timeout),
            )
        if result.returncode != 0:
            outputs.append(_analyze_failure_details(result))
    if not outputs:
        return None
    return ProjectAnalyzeResult(
        passed=False,
        detail="dart format failed for generated project",
        analyze_output="\n".join(outputs),
    )


def _validate_dart_project_inner(
    project_dir: Path,
    *,
    analyze_scope: str = "project",
    relative_paths: list[str] | None = None,
    dart: str | None = None,
    flutter: str | None = None,
    flutter_sdk: str | Path | None = None,
    skip_dart_format: bool = False,
) -> ProjectAnalyzeResult:
    """Run ``dart format`` and analyze; return structured outcome without raising."""
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

    format_target = (
        [str(path) for path in dart_targets]
        if scope_path_list
        else [str(project_dir / "lib")]
        if (project_dir / "lib").is_dir()
        else []
    )
    if format_target and not skip_dart_format:
        format_failure = _run_dart_format_targets(
            project_dir,
            dart=dart,
            format_target=format_target,
            timeout_sec=DART_FORMAT_TIMEOUT_SEC,
        )
        if format_failure is not None:
            return format_failure
    elif format_target and skip_dart_format:
        logger.info("Skipping dart format for planned analyze (analyze-only gate)")

    pub_get_failure = _run_flutter_pub_get(project_dir, flutter)
    if pub_get_failure is not None:
        return pub_get_failure

    analyze_command, tool_name = _build_analyze_command(
        dart=dart,
        flutter=flutter,
        scope_path_list=scope_path_list,
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


def _read_package_name(project_dir: Path) -> str:
    """Read the package name from ``pubspec.yaml``."""
    pubspec = project_dir / "pubspec.yaml"
    if not pubspec.is_file():
        return "demo_app"
    for line in pubspec.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip()
    return "demo_app"


_SKIP_IMPORT_PACKAGES = frozenset({"flutter", "flutter_test", "flutter_svg"})


def _validate_package_imports(planned: dict[str, str], package_name: str) -> str | None:
    """Return an error message when planned Dart uses the wrong package import prefix."""
    expected = f"package:{package_name}/"
    for path, content in planned.items():
        if not path.endswith(".dart"):
            continue
        for match in _PACKAGE_IMPORT.finditer(content):
            imported = match.group(1)
            if imported in _SKIP_IMPORT_PACKAGES:
                continue
            prefix = f"package:{imported}/"
            if prefix != expected:
                return (
                    f"{path} imports {prefix!r} but skeleton package is {package_name!r} "
                    f"(expected {expected!r})"
                )
    return None


def parse_format_failed_paths(details: str) -> tuple[str, ...]:
    """Return project-relative ``lib/…`` paths that ``dart format`` could not parse."""
    paths: list[str] = []
    for line in details.splitlines():
        match = _FORMAT_FAILED_PATH_RE.search(line)
        if match is None:
            continue
        paths.append(match.group("path").replace("\\", "/"))
    return tuple(dict.fromkeys(paths))


def parse_format_errors(details: str) -> list[str]:
    """Extract parser diagnostics from ``dart format`` failure output.

    Args:
        details: Combined stdout/stderr from a format invocation.

    Returns:
        Non-empty parser diagnostic lines, if any.
    """
    if "Could not format because the source could not be parsed" not in details:
        return []
    errors: list[str] = []
    for line in details.splitlines():
        stripped = line.strip()
        if _FORMAT_PARSE_ERROR_LINE.match(stripped):
            errors.append(stripped)
    return errors


def collect_analyze_error_lines(details: str, *, detail: str) -> tuple[str, ...]:
    """Merge analyzer and format parser diagnostics into one error tuple."""
    errors = parse_analyze_errors(details) or parse_format_errors(details)
    if errors:
        return tuple(errors)
    return (detail,)


_TEMP_ANALYZE_DIR_RE = re.compile(r"figma-flutter-spec23-[a-z0-9_]+", re.IGNORECASE)
_ABSOLUTE_DART_PATH_RE = re.compile(
    r"(?:[A-Za-z]:)?[/\\][^\s:]+[/\\](?P<basename>[^/\\:]+\.dart)",
    re.IGNORECASE,
)


def normalize_analyzer_errors_for_fingerprint(errors: tuple[str, ...]) -> tuple[str, ...]:
    """Strip volatile temp paths so repair loops detect repeated identical failures."""
    normalized: list[str] = []
    for error in errors:
        line = _TEMP_ANALYZE_DIR_RE.sub("<temp>", error)
        line = _ABSOLUTE_DART_PATH_RE.sub(r"\g<basename>", line)
        line = re.sub(
            r"line \d+, column \d+ of ",
            "line N, column M of ",
            line,
            count=1,
        )
        normalized.append(line)
    return tuple(normalized)


def parse_analyze_errors(details: str) -> list[str]:
    """Extract analyzer error lines from ``dart``/``flutter analyze`` output.

    Args:
        details: Combined stdout/stderr from an analyze invocation.

    Returns:
        Non-empty error diagnostic lines, if any.
    """
    errors: list[str] = []
    for line in details.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _ANALYZE_ERROR_LINE.search(stripped):
            errors.append(stripped)
    return errors


@dataclass(frozen=True)
class PlannedAnalyzeOutcome:
    """Result of analyzing planned Dart files in a temp skeleton project."""

    skipped: bool
    passed: bool
    detail: str
    errors: tuple[str, ...] = ()
    analyze_output: str = ""
    format_failed_paths: tuple[str, ...] = ()


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

    Returns:
        Structured analyze outcome including parsed error lines when analyze fails.
    """

    def _fail(
        detail: str,
        *,
        errors: tuple[str, ...],
        analyze_output: str = "",
        format_failed_paths: tuple[str, ...] = (),
    ) -> PlannedAnalyzeOutcome:
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

    if not _FLUTTER_SKELETON.is_dir():
        detail = f"flutter skeleton missing at {_FLUTTER_SKELETON}"
        return _fail(detail, errors=(detail,))

    import_error = _validate_package_imports(planned, package_name)
    if import_error is not None:
        return _fail(import_error, errors=(import_error,))

    planned = reconcile_planned_dart_files(planned)

    with tempfile.TemporaryDirectory(prefix="figma-flutter-spec23-") as tmp:
        project_dir = Path(tmp) / "analyze_check"
        shutil.copytree(_FLUTTER_SKELETON, project_dir)
        resolved_package = _read_package_name(project_dir)
        if resolved_package != package_name:
            import_error = _validate_package_imports(planned, resolved_package)
            if import_error is not None:
                return _fail(import_error, errors=(import_error,))
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
                    format_paths = tuple(
                        path for path in format_paths if path in widget_paths
                    ) or format_paths
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

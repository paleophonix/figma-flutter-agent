"""Dart source formatting (dart format) with size/minification guards."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger

from figma_flutter_agent.tools.process_run import run_subprocess

from .analyze import ProjectAnalyzeResult, _analyze_failure_details, _timeout_analyze_result
from .errors import collect_analyze_error_lines, parse_format_failed_paths
from .toolchain import _dart_format_target_detail, _read_package_name

_DART_FORMAT_PER_FILE_TIMEOUT_SEC = 6.0
_DART_FORMAT_BATCH_CAP_SEC = 90.0
_DART_FORMAT_BATCH_CHUNK_SIZE = 256
_DART_FORMAT_LARGE_FILE_BYTES = 50_000
# Formatter routinely hangs on 100KB+ generated layout/screen files; delimiters suffice.
_DART_FORMAT_SKIP_BYTES = 65_536
_DART_FORMAT_MINIFIED_LINE_CHARS = 4_000
_DART_FORMAT_LARGE_BASE_SEC = 12.0
_DART_FORMAT_BYTES_PER_EXTRA_SEC = 3_500.0
_DART_FORMAT_MAX_SINGLE_TIMEOUT_SEC = 90.0
_DART_FORMAT_BATCH_EXTRA_PER_FILE_SEC = 2.0
_DART_FORMAT_RECOVERY_PASSES = 2


def _dart_format_single_file_timeout(target: str) -> float:
    """Wall-clock budget for formatting one ``.dart`` file (scales with byte size)."""
    try:
        size = Path(target).stat().st_size
    except OSError:
        size = 0
    if size < _DART_FORMAT_LARGE_FILE_BYTES:
        return _DART_FORMAT_PER_FILE_TIMEOUT_SEC
    scaled = _DART_FORMAT_LARGE_BASE_SEC + size / _DART_FORMAT_BYTES_PER_EXTRA_SEC
    return min(_DART_FORMAT_MAX_SINGLE_TIMEOUT_SEC, scaled)


def _dart_format_batch_timeout(paths: list[str]) -> float:
    """Budget for one ``dart format`` invocation over explicit paths."""
    if not paths:
        return _DART_FORMAT_PER_FILE_TIMEOUT_SEC
    peak = max(_dart_format_single_file_timeout(path) for path in paths)
    extra_files = min(len(paths) - 1, 16)
    return min(
        _DART_FORMAT_BATCH_CAP_SEC,
        peak + extra_files * _DART_FORMAT_BATCH_EXTRA_PER_FILE_SEC,
    )


def _dart_format_per_file_timeout(target: str, *, file_count: int) -> float:
    """Return timeout for one file, or a batch estimate when only a count is known."""
    if file_count > 1:
        return min(
            _DART_FORMAT_BATCH_CAP_SEC,
            2.0 + _DART_FORMAT_PER_FILE_TIMEOUT_SEC * min(file_count, 16),
        )
    return _dart_format_single_file_timeout(target)


def _relative_dart_path(project_dir: Path, target: str) -> str:
    """Project-relative ``lib/…`` path for logs and parse-gate errors."""
    path = Path(target)
    if not path.is_absolute():
        path = project_dir / path
    try:
        return path.relative_to(project_dir).as_posix()
    except ValueError:
        return path.as_posix()


def _partition_format_targets_by_delimiters(
    project_dir: Path,
    targets: list[str],
) -> tuple[list[str], tuple[str, ...]]:
    """Split paths into format-ready vs delimiter-broken (skip ``dart format`` on broken)."""
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters
    from figma_flutter_agent.generator.writing.io import read_text_file

    ready: list[str] = []
    broken: list[str] = []
    for target in targets:
        try:
            content = read_text_file(Path(target))
        except OSError:
            broken.append(_relative_dart_path(project_dir, target))
            continue
        if validate_dart_delimiters(content) is not None:
            broken.append(_relative_dart_path(project_dir, target))
        else:
            ready.append(target)
    return ready, tuple(dict.fromkeys(broken))


def _delimiter_gate_format_failure(broken_paths: tuple[str, ...]) -> ProjectAnalyzeResult:
    """Synthetic format failure so recovery can target delimiter-broken files."""
    output = "\n".join(
        [
            "Could not format because the source could not be parsed.",
            *(
                f"line 1, column 1 of {path}: invalid Dart delimiters (skipped dart format)"
                for path in broken_paths
            ),
        ]
    )
    return ProjectAnalyzeResult(
        passed=False,
        detail="dart format failed for generated project",
        analyze_output=output,
    )


def _dart_format_file_targets(project_dir: Path, targets: list[str]) -> list[str]:
    """Keep only existing ``.dart`` files; never pass directories to ``dart format``."""
    resolved: list[str] = []
    for target in targets:
        path = Path(target)
        if not path.is_absolute():
            path = project_dir / path
        if path.is_dir():
            logger.warning(
                "Skipping dart format on directory {} (use explicit .dart paths only)",
                path.as_posix(),
            )
            continue
        if path.is_file() and path.suffix == ".dart":
            resolved.append(str(path))
    return resolved


def _dart_format_batch_size_summary(format_target: list[str], *, top: int = 5) -> str:
    """Largest targets (name, bytes, max line length) for diagnosing format hangs."""
    rows: list[tuple[int, str]] = []
    for target in format_target:
        path = Path(target)
        try:
            size = path.stat().st_size
            max_line = max((len(line) for line in path.read_text(encoding="utf-8").splitlines()), default=0)
        except OSError:
            size, max_line = 0, 0
        rows.append((size, f"{path.name}({size}B,L{max_line})"))
    rows.sort(key=lambda row: row[0], reverse=True)
    return ", ".join(label for _, label in rows[:top])


def _run_dart_format_batch(
    project_dir: Path,
    *,
    dart: str,
    format_target: list[str],
) -> ProjectAnalyzeResult | None:
    """Format many Dart files in one ``dart format`` invocation (explicit paths only)."""
    total = len(format_target)
    effective_timeout = _dart_format_batch_timeout(format_target)
    logger.info("Formatting {} Dart file(s) (batch)", total)
    try:
        result = run_subprocess(
            [dart, "format", *format_target],
            cwd=project_dir,
            label="dart format",
            timeout_sec=effective_timeout,
            timeout_log_level="warning",
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "dart format batch timed out after {:.0f}s; targets (largest first): {}",
            effective_timeout,
            _dart_format_batch_size_summary(format_target),
        )
        if all(_dart_format_timeout_allows_skip(path) for path in format_target):
            logger.warning(
                "dart format batch timed out after {:.0f}s; delimiter/minified skip",
                effective_timeout,
            )
            return None
        return _timeout_analyze_result("dart format (batch)", int(effective_timeout))
    if result.returncode != 0:
        return ProjectAnalyzeResult(
            passed=False,
            detail="dart format failed for generated project",
            analyze_output=_analyze_failure_details(result),
        )
    logger.info("dart format: {}/{} ok (batch)", total, total)
    return None


def _dart_source_passes_delimiter_gate(target: str) -> bool:
    """Return True when file contents pass structural delimiter validation."""
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters
    from figma_flutter_agent.generator.writing.io import read_text_file

    try:
        content = read_text_file(Path(target))
    except OSError:
        return False
    return validate_dart_delimiters(content) is None


def _dart_source_is_minified(target: str) -> bool:
    """Return True for single-line compiler emits that choke ``dart format``.

    Any Dart file (layout, cluster widget, etc.) emitted as one giant line makes
    ``dart format`` run quadratically on the line and hang for tens of seconds.
    Detection is path-independent — keyed on the longest line, not the directory.
    """
    path = Path(target)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not content.strip():
        return False
    max_line = max(len(line) for line in content.splitlines())
    return max_line >= _DART_FORMAT_MINIFIED_LINE_CHARS


def _dart_format_timeout_allows_skip(target: str) -> bool:
    """When ``dart format`` hangs, accept files that already pass delimiter validation."""
    if not _dart_source_passes_delimiter_gate(target):
        return False
    if _dart_source_is_minified(target):
        return True
    try:
        size = Path(target).stat().st_size
    except OSError:
        size = 0
    return size < _DART_FORMAT_SKIP_BYTES


def _filter_minified_layout_format_targets(
    project_dir: Path,
    files: list[str],
) -> list[str]:
    """Skip proactive ``dart format`` on minified single-line Dart emits (any path)."""
    kept: list[str] = []
    for target in files:
        path = Path(target)
        if not path.is_absolute():
            path = project_dir / path
        if _dart_source_is_minified(str(path)) and _dart_source_passes_delimiter_gate(
            str(path)
        ):
            logger.info(
                "Skipping dart format on minified emit {} (delimiter check passed)",
                _dart_format_target_detail(str(path)),
            )
            continue
        kept.append(target)
    return kept


def _filter_dart_format_targets_by_size(
    project_dir: Path,
    files: list[str],
) -> list[str]:
    """Drop very large files from ``dart format`` when delimiters already validate."""
    kept: list[str] = []
    for target in files:
        path = Path(target)
        if not path.is_absolute():
            path = project_dir / path
        try:
            size = path.stat().st_size
        except OSError:
            kept.append(target)
            continue
        if size < _DART_FORMAT_SKIP_BYTES:
            kept.append(target)
            continue
        if _dart_source_passes_delimiter_gate(target):
            logger.info(
                "Skipping dart format on {} ({} bytes); delimiter validation passed",
                _dart_format_target_detail(target),
                size,
            )
            continue
        kept.append(target)
    return kept


def _run_dart_format_single_file(
    project_dir: Path,
    *,
    dart: str,
    target: str,
) -> ProjectAnalyzeResult | None:
    per_timeout = _dart_format_single_file_timeout(target)
    try:
        result = run_subprocess(
            [dart, "format", target],
            cwd=project_dir,
            label="dart format",
            timeout_sec=per_timeout,
            timeout_log_level="warning",
        )
    except subprocess.TimeoutExpired:
        if _dart_format_timeout_allows_skip(target):
            logger.warning(
                "dart format timed out on {} ({}s) but delimiter check passed; skipping",
                _dart_format_target_detail(target),
                int(per_timeout),
            )
            return None
        detail = _dart_format_target_detail(target)
        return _timeout_analyze_result(f"dart format ({detail})", int(per_timeout))
    if result.returncode != 0:
        return ProjectAnalyzeResult(
            passed=False,
            detail="dart format failed for generated project",
            analyze_output=_analyze_failure_details(result),
        )
    return None


def _partition_format_targets_by_size(
    paths: list[str],
) -> tuple[list[str], list[str]]:
    """Split explicit ``.dart`` paths into below/above the large-file byte threshold."""
    small: list[str] = []
    large: list[str] = []
    for path in paths:
        try:
            size = Path(path).stat().st_size
        except OSError:
            size = 0
        if size >= _DART_FORMAT_LARGE_FILE_BYTES:
            large.append(path)
        else:
            small.append(path)
    return small, large


def _run_dart_format_per_file_sequential(
    project_dir: Path,
    *,
    dart: str,
    format_target: list[str],
) -> ProjectAnalyzeResult | None:
    for target in format_target:
        failure = _run_dart_format_single_file(
            project_dir,
            dart=dart,
            target=target,
        )
        if failure is not None:
            return failure
    return None


def _run_dart_format_after_batch_timeout(
    project_dir: Path,
    *,
    dart: str,
    format_target: list[str],
) -> ProjectAnalyzeResult | None:
    """Retry after batch timeout without spawning one ``dart format`` per small file."""
    small, large = _partition_format_targets_by_size(format_target)
    logger.info(
        "dart format batch retry: {} small file(s), {} large file(s)",
        len(small),
        len(large),
    )
    if small:
        failure = _run_dart_format_batch(
            project_dir,
            dart=dart,
            format_target=small,
        )
        if failure is not None:
            if "timed out" in failure.detail:
                if all(_dart_format_timeout_allows_skip(path) for path in small):
                    logger.warning(
                        "dart format small-file batch timed out ({} file(s)); skip",
                        len(small),
                    )
                    failure = None
                else:
                    logger.warning(
                        "dart format small-file batch timed out ({} file(s)); per-file",
                        len(small),
                    )
                    failure = _run_dart_format_per_file_sequential(
                        project_dir,
                        dart=dart,
                        format_target=small,
                    )
            if failure is not None:
                return failure
    for target in large:
        failure = _run_dart_format_single_file(
            project_dir,
            dart=dart,
            target=target,
        )
        if failure is not None:
            return failure
    return None


def _run_dart_format_on_files(
    project_dir: Path,
    *,
    dart: str,
    files: list[str],
) -> ProjectAnalyzeResult | None:
    """Run batch/per-file ``dart format`` on delimiter-valid paths only."""
    total = len(files)
    if total == 0:
        return None
    if total == 1:
        return _run_dart_format_single_file(
            project_dir,
            dart=dart,
            target=files[0],
        )
    if total > _DART_FORMAT_BATCH_CHUNK_SIZE:
        for index in range(0, total, _DART_FORMAT_BATCH_CHUNK_SIZE):
            chunk = files[index : index + _DART_FORMAT_BATCH_CHUNK_SIZE]
            failure = _run_dart_format_batch(
                project_dir,
                dart=dart,
                format_target=chunk,
            )
            if failure is None:
                continue
            if "timed out" in failure.detail:
                logger.warning(
                    "dart format batch timed out for {} file(s); retrying by size",
                    len(chunk),
                )
                failure = _run_dart_format_after_batch_timeout(
                    project_dir,
                    dart=dart,
                    format_target=chunk,
                )
            if failure is not None:
                return failure
        return None
    failure = _run_dart_format_batch(
        project_dir,
        dart=dart,
        format_target=files,
    )
    if failure is not None and "timed out" in failure.detail:
        logger.warning(
            "dart format batch timed out for {} file(s); retrying by size",
            total,
        )
        return _run_dart_format_after_batch_timeout(
            project_dir,
            dart=dart,
            format_target=files,
        )
    return failure


def _run_dart_format_targets(
    project_dir: Path,
    *,
    dart: str,
    format_target: list[str],
) -> ProjectAnalyzeResult | None:
    """Format explicit Dart file paths; batch in chunks (Windows-friendly)."""
    files = _dart_format_file_targets(project_dir, format_target)
    ready, broken = _partition_format_targets_by_delimiters(project_dir, files)
    if broken:
        logger.warning(
            "Delimiter gate: skipping dart format on {} file(s) (fail-fast)",
            len(broken),
        )
    if not ready:
        if broken:
            return _delimiter_gate_format_failure(broken)
        return None
    ready = _filter_dart_format_targets_by_size(project_dir, ready)
    ready = _filter_minified_layout_format_targets(project_dir, ready)
    if not ready:
        if broken:
            return _delimiter_gate_format_failure(broken)
        return None
    failure = _run_dart_format_on_files(project_dir, dart=dart, files=ready)
    if failure is not None:
        return failure
    if broken:
        return _delimiter_gate_format_failure(broken)
    return None


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

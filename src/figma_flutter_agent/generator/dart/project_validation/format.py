"""Dart source formatting (dart format) with size/minification guards."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger

from figma_flutter_agent.tools.process_run import run_subprocess

from .analyze import ProjectAnalyzeResult, _analyze_failure_details, _timeout_analyze_result
from .format_limits import (
    _DART_FORMAT_BATCH_CHUNK_SIZE,
    _DART_FORMAT_SKIP_BYTES,
    _dart_format_batch_size_summary,
    _dart_format_batch_timeout,
    _dart_format_single_file_timeout,
    _dart_format_timeout_allows_skip,
    _dart_source_is_minified,
    _dart_source_passes_delimiter_gate,
    _partition_format_targets_by_size,
    _relative_dart_path,
)
from .toolchain import _dart_format_target_detail


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
        if _dart_source_is_minified(str(path)) and _dart_source_passes_delimiter_gate(str(path)):
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

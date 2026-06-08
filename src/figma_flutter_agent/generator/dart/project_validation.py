"""Post-generation Dart validation."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from figma_flutter_agent.dart_error_log import record_dart_analyze_failure
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.fixtures.screens_manifest import fixtures_root
from figma_flutter_agent.generator.planned.reconcile import (
    reconcile_planned_dart_files,
    refresh_shrunk_and_delegate_planned_widgets,
)
from figma_flutter_agent.generator.writing.core import DartWriter
from figma_flutter_agent.tools.process_run import (
    DART_ANALYZE_TIMEOUT_SEC,
    FLUTTER_PUB_GET_TIMEOUT_SEC,
    run_subprocess,
)

if TYPE_CHECKING:
    from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens

_FLUTTER_SKELETON = fixtures_root() / "flutter_skeleton"
_PACKAGE_IMPORT = re.compile(r"""import\s+['"]package:([^/'"]+)/""")
_WINDOWS_ZONE_IDENTIFIER_NOISE = re.compile(
    r"^Unblock-File:.*Zone\.Identifier['\"]?\.\s*$",
    re.MULTILINE,
)
_ANALYZE_ERROR_LINE = re.compile(r"^\s*error\s+-", re.MULTILINE)
_ANALYZE_WARNING_LINE = re.compile(r"^\s*warning\s+-", re.MULTILINE)
_FORMAT_PARSE_ERROR_LINE = re.compile(
    r"^line \d+, column \d+ of .+?: .+$",
    re.MULTILINE,
)
_FORMAT_FAILED_PATH_RE = re.compile(
    r"line \d+, column \d+ of .*?(?P<path>lib[/\\][^\s:]+\.dart)",
    re.IGNORECASE,
)
def _dart_format_target_detail(target: str) -> str:
    """Path label for logs; include file size when the target exists on disk."""
    rel = target.replace("\\", "/")
    path = Path(target)
    if path.is_file():
        return f"{rel} ({path.stat().st_size:,} bytes)"
    return rel


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


def _strip_windows_zone_identifier_noise(text: str | None) -> str:
    """Remove Flutter SDK ``Unblock-File`` noise from captured CLI stderr."""
    if not text:
        return ""
    cleaned = _WINDOWS_ZONE_IDENTIFIER_NOISE.sub("", text)
    return cleaned.strip()


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


def _run_flutter_pub_get(
    project_dir: Path,
    flutter: str | None,
    *,
    pubspec_changed: bool | None = None,
    force: bool = False,
) -> ProjectAnalyzeResult | None:
    """Resolve packages in a Flutter project before analyze. Returns failure or None."""
    from figma_flutter_agent.generator.codegen import run_pub_get

    if flutter is None:
        return None
    pubspec = project_dir / "pubspec.yaml"
    if not pubspec.is_file():
        return None
    try:
        run_pub_get(
            project_dir,
            pubspec_changed=pubspec_changed,
            force=force,
        )
    except GenerationError as exc:
        detail = str(exc)
        if "timed out" in detail:
            return _timeout_analyze_result("flutter pub get", FLUTTER_PUB_GET_TIMEOUT_SEC)
        return ProjectAnalyzeResult(
            passed=False,
            detail="flutter pub get failed before analyze",
            analyze_output=detail,
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


_DART_ANALYZE_CHUNK_SIZE = 6


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
    for chunk_index, chunk in enumerate(chunks, start=1):
        command, _ = _build_analyze_command(
            dart=dart,
            flutter=None,
            scope_path_list=True,
            dart_targets=chunk,
            project_dir=project_dir,
        )
        timeout = _dart_analyze_timeout_sec(chunk)
        label = (
            f"{tool_name} ({chunk_index}/{len(chunks)})"
            if len(chunks) > 1
            else tool_name
        )
        try:
            analyze_result = run_subprocess(
                command,
                cwd=project_dir,
                label=label,
                timeout_sec=timeout,
            )
        except subprocess.TimeoutExpired:
            return _timeout_analyze_result(label, timeout)
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


@dataclass(frozen=True)
class ProjectAnalyzeResult:
    """Outcome of format/analyze against a on-disk Flutter project."""

    passed: bool
    detail: str
    analyze_output: str = ""


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
        if not _FLUTTER_SKELETON.is_dir():
            msg = f"flutter skeleton missing at {_FLUTTER_SKELETON}"
            raise FileNotFoundError(msg)
        temp_dir = tempfile.TemporaryDirectory(prefix="figma-flutter-spec23-")
        project_dir = Path(temp_dir.name) / "analyze_check"
        shutil.copytree(_FLUTTER_SKELETON, project_dir)
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


def align_skeleton_pubspec_package_name(project_dir: Path, package_name: str) -> None:
    """Rewrite the temp skeleton ``pubspec.yaml`` name to match the target Flutter app.

    The analyze/parse-gate harness copies ``tests/fixtures/flutter_skeleton`` (default
    ``name: demo_app``). Planned Dart for ``demo_app2`` and other apps must keep their
    ``package:<app>/`` imports while ``dart format`` / ``dart analyze`` run in the temp tree.

    Args:
        project_dir: Temporary Flutter project root (skeleton copy).
        package_name: Package name from the real project's ``pubspec.yaml``.
    """
    pubspec = project_dir / "pubspec.yaml"
    if not pubspec.is_file():
        return
    lines = pubspec.read_text(encoding="utf-8").splitlines(keepends=True)
    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.strip().startswith("name:"):
            updated.append(f"name: {package_name}\n")
            replaced = True
        else:
            updated.append(line if line.endswith("\n") else f"{line}\n")
    if not replaced:
        updated.insert(0, f"name: {package_name}\n")
    pubspec.write_text("".join(updated), encoding="utf-8")


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


def summarize_analyze_diagnostics(
    details: str, *, detail: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split analyzer output into (errors, warnings) tuples.

    Args:
        details: Combined stdout/stderr from an analyze invocation.
        detail: Human-readable label used only when no lines are matched.

    Returns:
        ``(errors, warnings)`` — each a tuple of stripped diagnostic lines.
    """
    errors: list[str] = []
    warnings: list[str] = []
    for line in details.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _ANALYZE_ERROR_LINE.search(stripped):
            errors.append(stripped)
        elif _ANALYZE_WARNING_LINE.search(stripped):
            warnings.append(stripped)
    return tuple(errors), tuple(warnings)


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


def _planned_delimiter_error_messages(planned: dict[str, str]) -> list[str]:
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    errors: list[str] = []
    for path, content in planned.items():
        if not path.endswith(".dart"):
            continue
        delimiter_error = validate_dart_delimiters(content)
        if delimiter_error is not None:
            errors.append(f"{path}: {delimiter_error}")
    return errors


def _repair_or_fallback_planned_delimiter_errors(
    planned: dict[str, str],
    *,
    package_name: str,
) -> list[str]:
    """Repair delimiter issues in planned Dart; layout-fallback broken screens before failing."""
    from figma_flutter_agent.generator.dart.syntax_repairs import (
        apply_planned_delimiter_balance,
        repair_planned_dart_delimiters_if_needed,
    )
    from figma_flutter_agent.generator.dart.llm_codegen import repair_dart_delimiters
    from figma_flutter_agent.generator.planned.reconcile import (
        fallback_unparseable_screens_to_layout,
        sanitize_screen_emit_syntax,
    )

    for _ in range(4):
        broken_paths = [
            path.split(":", 1)[0]
            for path in _planned_delimiter_error_messages(planned)
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

    broken_paths = [
        path.split(":", 1)[0]
        for path in _planned_delimiter_error_messages(planned)
    ]
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
) -> PlannedAnalyzeOutcome:
    """Fail-fast when planned Dart is not parseable (dart format only, temp tree).

    Writes ``planned`` into the flutter skeleton workspace and runs ``dart format``
    on each file. Does not run ``dart analyze`` — use :func:`analyze_planned_dart_files`
    for full spec23 gates.
    """
    if not planned:
        return PlannedAnalyzeOutcome(skipped=True, passed=True, detail="no planned dart files")

    from figma_flutter_agent.generator.planned.reconcile import canonicalize_planned_path_keys

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

    from figma_flutter_agent.generator.dart.syntax_repairs import (
        repair_planned_dart_delimiters_if_needed,
    )
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

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

    if not _FLUTTER_SKELETON.is_dir():
        detail = f"flutter skeleton missing at {_FLUTTER_SKELETON}"
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
        shutil.copytree(_FLUTTER_SKELETON, project_dir)
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
            dart_targets = [
                str(project_dir / path.replace("\\", "/")) for path in sorted(planned)
            ]
        if format_outcome is not None:
            format_paths = parse_format_failed_paths(format_outcome.analyze_output)
            fallback_unparseable_screens_to_layout(
                planned,
                format_paths,
                package_name=package_name,
            )
            writer.write_files(planned)
            dart_targets = [
                str(project_dir / path.replace("\\", "/"))
                for path in sorted(planned)
            ]
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

    from figma_flutter_agent.generator.planned.reconcile import ensure_planned_widget_manifest

    ensure_planned_widget_manifest(planned)

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
        shutil.copytree(_FLUTTER_SKELETON, project_dir)
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

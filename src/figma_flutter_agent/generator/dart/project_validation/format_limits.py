"""Timeout/size/minification heuristics for ``dart format`` invocations."""

from __future__ import annotations

from pathlib import Path

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


def _dart_format_batch_size_summary(format_target: list[str], *, top: int = 5) -> str:
    """Largest targets (name, bytes, max line length) for diagnosing format hangs."""
    rows: list[tuple[int, str]] = []
    for target in format_target:
        path = Path(target)
        try:
            size = path.stat().st_size
            max_line = max(
                (len(line) for line in path.read_text(encoding="utf-8").splitlines()), default=0
            )
        except OSError:
            size, max_line = 0, 0
        rows.append((size, f"{path.name}({size}B,L{max_line})"))
    rows.sort(key=lambda row: row[0], reverse=True)
    return ", ".join(label for _, label in rows[:top])


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

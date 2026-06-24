"""Expand single-line minified Dart emits before toolchain analyze."""

from __future__ import annotations

from pathlib import Path

from .format_limits import _DART_FORMAT_MINIFIED_LINE_CHARS, _dart_source_is_minified


def expand_minified_dart_source(
    content: str,
    *,
    threshold: int = _DART_FORMAT_MINIFIED_LINE_CHARS,
) -> str:
    """Break physical lines longer than ``threshold`` so ``dart analyze`` stays linear.

    Wrapping only commits when delimiter validation still passes; otherwise the
    original minified source is returned unchanged.

    Args:
        content: Dart source text.
        threshold: Max allowed physical line length before wrapping.

    Returns:
        Source with long lines split when safe; unchanged when already multiline
        or when no delimiter-safe wrap exists.
    """
    if not content:
        return content
    lines = content.splitlines()
    if not lines:
        return content
    if max(len(line) for line in lines) < threshold:
        return content
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(_wrap_minified_physical_line(line, threshold=threshold))
    suffix = "\n" if content.endswith("\n") else ""
    expanded = "\n".join(wrapped) + suffix
    if _expand_preserves_syntax(content, expanded):
        return expanded
    return content


def expand_minified_dart_source_for_readability(
    content: str,
    *,
    threshold: int = _DART_FORMAT_MINIFIED_LINE_CHARS,
    max_passes: int = 12,
) -> str:
    """Repeatedly wrap minified Dart for debug-bundle triage readability.

    Unlike :func:`expand_minified_dart_source`, this path may split long physical
    lines even when fragment-level delimiter probes fail, because debug bundles
    are not compiled.

    Args:
        content: Dart source text.
        threshold: Max allowed physical line length.
        max_passes: Upper bound on wrap iterations.

    Returns:
        Source with long lines split for human inspection.
    """
    if not content:
        return content
    expanded = content
    for _ in range(max_passes):
        lines = expanded.splitlines()
        if not lines or max(len(line) for line in lines) < threshold:
            break
        wrapped: list[str] = []
        for line in lines:
            wrapped.extend(_wrap_physical_line_for_readability(line, threshold=threshold))
        suffix = "\n" if expanded.endswith("\n") else ""
        next_pass = "\n".join(wrapped) + suffix
        if next_pass == expanded:
            break
        expanded = next_pass
    return expanded


def _wrap_physical_line_for_readability(line: str, *, threshold: int) -> list[str]:
    """Split one physical line for debug triage without compile-time validation."""
    if len(line) <= threshold:
        return [line]
    indent = len(line) - len(line.lstrip(" "))
    continuation = " " * (indent + 2)
    segments: list[str] = []
    remaining = line
    while len(remaining) > threshold:
        limit = min(threshold, len(remaining))
        split_end = -1
        for needle, end_offset in (("), ", 2), (", ", 1), ("),", 1), ("],", 1), ("},", 1)):
            pos = remaining.rfind(needle, 0, limit)
            if pos >= 0:
                split_end = pos + end_offset
                break
        if split_end < 0:
            split_end = limit
        if split_end <= 0:
            break
        segments.append(remaining[:split_end].rstrip())
        remaining = continuation + remaining[split_end:].lstrip()
    segments.append(remaining)
    return segments


def expand_minified_planned_sources(planned: dict[str, str]) -> dict[str, str]:
    """Return a copy of ``planned`` with minified ``.dart`` bodies expanded for analyze."""
    expanded: dict[str, str] = {}
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if normalized.endswith(".dart"):
            expanded[path] = expand_minified_dart_source(content)
        else:
            expanded[path] = content
    return expanded


def prepare_project_dart_for_analyze(project_dir: Path, dart_paths: list[str]) -> None:
    """Rewrite minified on-disk Dart files with wrapped physical lines before analyze."""
    for relative in dart_paths:
        if not relative.endswith(".dart"):
            continue
        candidate = project_dir / relative
        if not candidate.is_file():
            continue
        if not _dart_source_is_minified(str(candidate)):
            continue
        original = candidate.read_text(encoding="utf-8")
        candidate.write_text(
            expand_minified_dart_source(original),
            encoding="utf-8",
            newline="\n",
        )


def _expand_preserves_syntax(original: str, expanded: str) -> bool:
    """Return True when wrapping did not break delimiter structure."""
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    if expanded == original:
        return True
    if validate_dart_delimiters(original) is not None:
        return False
    return validate_dart_delimiters(expanded) is None


def _wrap_minified_physical_line(line: str, *, threshold: int) -> list[str]:
    """Split one physical line into shorter lines without changing Dart semantics."""
    if len(line) <= threshold:
        return [line]
    indent = len(line) - len(line.lstrip(" "))
    continuation = " " * (indent + 2)
    segments: list[str] = []
    remaining = line
    while len(remaining) > threshold:
        split_end = _find_delimiter_safe_split_end(
            remaining,
            threshold=threshold,
            continuation=continuation,
        )
        if split_end < 0:
            break
        segments.append(remaining[:split_end].rstrip())
        remaining = continuation + remaining[split_end:].lstrip()
    segments.append(remaining)
    return segments


def _find_delimiter_safe_split_end(
    remaining: str,
    *,
    threshold: int,
    continuation: str,
) -> int:
    """Return exclusive end index for the first wrapped segment, or ``-1``."""
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    limit = min(threshold, len(remaining))
    for end in _candidate_split_end_indices(remaining, limit):
        head = remaining[:end].rstrip()
        tail_body = remaining[end:].lstrip()
        if not head or not tail_body:
            continue
        probe = f"{head}\n{continuation}{tail_body}"
        if validate_dart_delimiters(probe) is None:
            return end
    return -1


def _candidate_split_end_indices(remaining: str, limit: int) -> list[int]:
    """Collect delimiter split candidates before ``limit``, longest first."""
    indices: list[int] = []
    for needle, end_offset in (("), ", 2), (", ", 1), ("),", 1), ("],", 1), ("},", 1)):
        start = 0
        while start < limit:
            pos = remaining.find(needle, start, limit)
            if pos < 0:
                break
            indices.append(pos + end_offset)
            start = pos + len(needle)
    return sorted(set(indices), reverse=True)

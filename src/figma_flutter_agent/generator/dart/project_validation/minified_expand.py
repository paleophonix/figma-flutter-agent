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

    Args:
        content: Dart source text.
        threshold: Max allowed physical line length before wrapping.

    Returns:
        Source with long lines split; unchanged when already multiline.
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
    return "\n".join(wrapped) + suffix


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


def _wrap_minified_physical_line(line: str, *, threshold: int) -> list[str]:
    """Split one physical line into shorter lines without changing Dart semantics."""
    if len(line) <= threshold:
        return [line]
    indent = len(line) - len(line.lstrip(" "))
    continuation = " " * (indent + 2)
    segments: list[str] = []
    remaining = line
    while len(remaining) > threshold:
        split_at = remaining.rfind("), ", 0, threshold)
        if split_at < 0:
            split_at = remaining.rfind(", ", 0, threshold)
        if split_at < 0:
            break
        segments.append(remaining[: split_at + 1])
        remaining = continuation + remaining[split_at + 2 :].lstrip()
    segments.append(remaining)
    return segments

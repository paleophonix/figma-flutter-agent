"""Widget pruning passes — drop duplicate, unreferenced, and unparseable planned widgets."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from loguru import logger

from .class_inspect import (
    _pick_canonical_widget_path,
    _planned_has_widget_consumers,
    _widget_class_names_by_path,
    _widget_class_paths,
    transitively_referenced_widget_paths,
)
from .hydrate import _sanitize_ingested_widget_source
from .paths import _normalized_widget_stem


def _widget_class_root_name(class_name: str) -> str | None:
    """Return the base widget class when ``class_name`` is a numbered stem alias."""
    match = re.match(r"^(.+Widget)\d+$", class_name)
    if match is None:
        return None
    return match.group(1)


def collapse_numbered_widget_stem_aliases(planned: dict[str, str]) -> dict[str, str]:
    """Rewrite numbered widget ctor aliases to the canonical class and drop alias files."""
    class_paths = _widget_class_paths(planned)
    canonical_by_stem: dict[str, str] = {}
    for class_name, path in class_paths.items():
        if re.search(r"\d+$", class_name):
            continue
        canonical_by_stem[_normalized_widget_stem(Path(path).stem)] = class_name

    alias_to_canonical: dict[str, str] = {}
    drop_paths: set[str] = set()
    for class_name, path in class_paths.items():
        root = _widget_class_root_name(class_name)
        if root is None:
            continue
        stem = _normalized_widget_stem(Path(path).stem)
        canonical = canonical_by_stem.get(stem) or (
            root if root in class_paths and not re.search(r"\d+$", root) else None
        )
        if canonical is None or canonical == class_name:
            continue
        alias_to_canonical[class_name] = canonical
        drop_paths.add(path)

    if not alias_to_canonical:
        return planned

    updated = dict(planned)
    for path, content in list(updated.items()):
        normalized = path.replace("\\", "/")
        if not normalized.endswith(".dart"):
            continue
        patched = content
        for alias, canonical in sorted(
            alias_to_canonical.items(), key=lambda item: len(item[0]), reverse=True
        ):
            patched = patched.replace(f"const {alias}(", f"const {canonical}(")
            patched = patched.replace(f"{alias}(", f"{canonical}(")
        if patched != content:
            updated[path] = patched
    for path in drop_paths:
        updated.pop(path, None)
        logger.info("Collapsed numbered widget alias file: {}", path.replace("\\", "/"))
    return updated


def strip_inline_widget_duplicates_from_screen(
    screen_code: str,
    planned_files: Mapping[str, str],
) -> str:
    """Remove widget classes inlined in a screen when ``lib/widgets`` already defines them."""
    from figma_flutter_agent.generator.dart.llm_codegen import _safe_strip_widget_class_definition

    class_paths = _widget_class_paths(dict(planned_files))
    if not class_paths:
        return screen_code

    content = screen_code
    for class_name in sorted(class_paths, key=len, reverse=True):
        if not re.search(
            rf"class\s+{re.escape(class_name)}\s+extends\s+",
            content,
        ):
            continue
        stripped = _safe_strip_widget_class_definition(
            content,
            class_name,
            strip_state=True,
        )
        if stripped == content:
            continue
        logger.info(
            "Removed inline {} from screen (canonical {})",
            class_name,
            class_paths[class_name],
        )
        content = stripped
    return content.rstrip() + ("\n" if screen_code.endswith("\n") else "")


def strip_inline_widget_duplicates_from_screens(planned: dict[str, str]) -> dict[str, str]:
    """Remove widget class bodies inlined in screen files when ``lib/widgets`` owns them."""
    class_paths = _widget_class_paths(planned)
    if not class_paths:
        return planned

    updated = dict(planned)
    for path, content in list(planned.items()):
        if not path.endswith("_screen.dart"):
            continue
        patched = strip_inline_widget_duplicates_from_screen(content, planned)
        if patched != content:
            updated[path] = patched
    return updated


def prune_duplicate_widget_classes(planned: dict[str, str]) -> dict[str, str]:
    """Drop duplicate widget files that redeclare the same public widget class."""
    by_class: dict[str, list[str]] = {}
    for path, class_name in _widget_class_names_by_path(planned).items():
        by_class.setdefault(class_name, []).append(path)

    drop_paths: set[str] = set()
    for paths in by_class.values():
        if len(paths) < 2:
            continue
        canonical = _pick_canonical_widget_path(paths, planned)
        drop_paths.update(path for path in paths if path != canonical)

    if not drop_paths:
        return planned

    updated = dict(planned)
    for path in drop_paths:
        updated.pop(path, None)
    return updated


def prune_unreferenced_planned_widgets(planned: dict[str, str]) -> dict[str, str]:
    """Drop ``lib/widgets`` files not referenced from layout, screens, or other widgets."""
    if not _planned_has_widget_consumers(planned):
        return planned
    referenced = transitively_referenced_widget_paths(planned)
    updated = dict(planned)
    for path in list(updated.keys()):
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/") or not normalized.endswith(".dart"):
            continue
        if path in referenced:
            continue
        updated.pop(path, None)
        logger.info("Pruned unreferenced planned widget: {}", normalized)
    return updated


def drop_unparseable_planned_widget_files(planned: dict[str, str]) -> dict[str, str]:
    """Remove or repair ``lib/widgets`` bodies that fail delimiter validation after sanitize."""
    from figma_flutter_agent.generator.dart.llm_codegen import (
        repair_dart_delimiters,
        validate_dart_delimiters,
    )

    has_consumers = _planned_has_widget_consumers(planned)
    referenced = transitively_referenced_widget_paths(planned) if has_consumers else set()
    updated = dict(planned)
    for path, content in list(updated.items()):
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/widgets/") or not normalized.endswith(".dart"):
            continue
        sanitized = _sanitize_ingested_widget_source(content, widget_path=normalized)
        if validate_dart_delimiters(sanitized) is None:
            if sanitized != content:
                updated[path] = sanitized
            continue
        if has_consumers and path not in referenced:
            updated.pop(path, None)
            from figma_flutter_agent.pipeline.warning_policy import log_recoverable

            log_recoverable(
                "Dropped unparseable unreferenced planned widget: {}",
                normalized,
            )
            continue
        repaired = repair_dart_delimiters(sanitized)
        if validate_dart_delimiters(repaired) is None:
            updated[path] = repaired
            logger.info("Repaired delimiter damage in referenced widget: {}", normalized)
            continue
        logger.warning(
            "Referenced planned widget still unparseable after repair: {}",
            normalized,
        )
    return updated

"""Disk recovery and widget absorption."""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from .class_inspect import (
    _is_foreign_delegate_widget_build,
    _is_self_referential_widget_build,
    _is_shrink_only_widget_source,
    _widget_class_paths,
)
from .paths import _normalized_widget_stem, _widget_lib_path_for_class

_HYDRATE_SHA_MARKER_RE = re.compile(
    r"^// figma-flutter-hydrate-sha256:([a-f0-9]{64})\n",
    re.MULTILINE,
)


def _any_widget_needs_disk_recovery(planned) -> bool:
    for class_name, path in _widget_class_paths(planned).items():
        if _widget_body_needs_recovery(planned.get(path, ""), class_name):
            return True
    return False


def _sanitize_ingested_widget_source(
    source: str,
    *,
    widget_path: str | None = None,
    package_name: str | None = None,
) -> str:
    """Delimiter/orphan fixes for renderer-produced bodies (codegen AST already ran)."""
    from figma_flutter_agent.generator.dart.postprocess import (
        ensure_app_layout_import,
        ensure_dart_ui_import,
        strip_self_widget_import,
    )
    from figma_flutter_agent.generator.dart.syntax_repairs import sanitize_planned_widget_syntax

    updated = sanitize_planned_widget_syntax(source)
    updated = ensure_app_layout_import(updated, package_name=package_name)
    updated = ensure_dart_ui_import(updated)
    if widget_path is not None:
        updated = strip_self_widget_import(updated, widget_path=widget_path)
    return updated


def _widget_body_needs_recovery(content: str, class_name: str) -> bool:
    if _is_self_referential_widget_build(content, class_name):
        return True
    if _is_foreign_delegate_widget_build(content, class_name):
        return True
    if len(content) > 500 and "Stack(" in content:
        return False
    return not ("SvgPicture.asset" in content or "Positioned(" in content)


def absorb_disk_widget_alias_bodies(
    planned: dict[str, str],
    project_dir: Path | None,
) -> dict[str, str]:
    """Replace stub widget sources with a richer on-disk file sharing the same class."""
    if project_dir is None or not project_dir.is_dir():
        return planned

    widgets_dir = project_dir / "lib" / "widgets"
    if not widgets_dir.is_dir():
        return planned

    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    updated = dict(planned)
    for class_name, canon_path in _widget_class_paths(updated).items():
        content = updated.get(canon_path, "")
        if not _widget_body_needs_recovery(content, class_name):
            continue
        canon_norm = _normalized_widget_stem(Path(canon_path).stem)
        best_rel: str | None = None
        best_source: str | None = None
        best_score = -1
        for dart_file in widgets_dir.glob("*.dart"):
            rel = f"lib/widgets/{dart_file.name}"
            if rel == canon_path:
                continue
            if _normalized_widget_stem(dart_file.stem) != canon_norm:
                continue
            disk_source = dart_file.read_text(encoding="utf-8")
            if not re.search(rf"class\s+{re.escape(class_name)}\s+extends", disk_source):
                continue
            if _is_self_referential_widget_build(disk_source, class_name):
                continue
            score = len(disk_source)
            if score > best_score:
                best_score = score
                best_rel = rel
                best_source = disk_source
        if best_source is None or best_rel is None:
            continue
        disk_source = _sanitize_ingested_widget_source(best_source)
        if validate_dart_delimiters(disk_source) is not None:
            logger.warning(
                "Skipping absorb {} for {}: invalid Dart after sanitize",
                best_rel,
                class_name,
            )
            continue
        updated[canon_path] = disk_source
        logger.info(
            "Absorbed widget body for {} from disk alias {}",
            class_name,
            best_rel,
        )
    return updated


def _hydrate_content_digest(source: str) -> str:
    import hashlib

    body = _HYDRATE_SHA_MARKER_RE.sub("", source, count=1)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _stamp_hydrate_digest(source: str, digest: str) -> str:
    body = _HYDRATE_SHA_MARKER_RE.sub("", source, count=1)
    return f"// figma-flutter-hydrate-sha256:{digest}\n{body}"


def hydrate_planned_widget_files_from_project(
    planned: dict[str, str],
    project_dir: Path | None,
) -> dict[str, str]:
    """Merge on-disk ``lib/widgets`` bodies referenced by screens into ``planned``."""
    if project_dir is None or not project_dir.is_dir():
        return planned

    updated = dict(planned)
    widget_use_re = re.compile(r"const\s+(\w+Widget)\s*\(")
    for path, content in planned.items():
        if not path.endswith("_screen.dart"):
            continue
        for class_name in sorted(set(widget_use_re.findall(content))):
            widget_rel = _widget_lib_path_for_class(class_name)
            existing = updated.get(widget_rel)
            if (
                existing is not None
                and not _is_shrink_only_widget_source(existing)
                and not _is_foreign_delegate_widget_build(existing, class_name)
            ):
                continue
            disk_path = project_dir / widget_rel
            if not disk_path.is_file():
                continue
            disk_source = disk_path.read_text(encoding="utf-8")
            if _is_shrink_only_widget_source(disk_source):
                continue
            if _is_foreign_delegate_widget_build(disk_source, class_name):
                continue
            from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

            disk_source = _sanitize_ingested_widget_source(disk_source)
            if validate_dart_delimiters(disk_source) is not None:
                logger.warning(
                    "Skipping hydrate {} from disk: invalid Dart after sanitize",
                    widget_rel,
                )
                continue
            disk_digest = _hydrate_content_digest(disk_source)
            if existing is not None and _hydrate_content_digest(existing) == disk_digest:
                continue
            updated[widget_rel] = _stamp_hydrate_digest(disk_source, disk_digest)
            logger.debug(
                "Hydrated {} from project disk for {}",
                widget_rel,
                class_name,
            )
    return updated


def prune_disk_widget_stem_aliases(
    project_dir: Path,
    planned: dict[str, str],
) -> list[str]:
    """Delete on-disk widget files that alias the canonical planned path for a class."""
    widgets_dir = project_dir / "lib" / "widgets"
    if not widgets_dir.is_dir():
        return []

    canonical_paths = {p.replace("\\", "/") for p in _widget_class_paths(planned).values()}
    if not canonical_paths:
        return []

    canonical_norms = {_normalized_widget_stem(Path(path).stem) for path in canonical_paths}
    removed: list[str] = []
    for dart_file in sorted(widgets_dir.glob("*.dart")):
        rel = f"lib/widgets/{dart_file.name}"
        if rel in canonical_paths:
            continue
        norm = _normalized_widget_stem(dart_file.stem)
        if norm not in canonical_norms:
            continue
        try:
            dart_file.unlink()
            removed.append(rel)
            logger.info("Removed stale widget alias on disk: {}", rel)
        except OSError as exc:
            logger.warning("Could not remove stale widget alias {}: {}", rel, exc)
    return removed


def align_widget_class_with_file_stem(planned: dict[str, str]) -> dict[str, str]:
    """Rename a widget class when the declared name disagrees with ``lib/widgets/<stem>.dart``."""
    from figma_flutter_agent.generator.layout.common import to_pascal_case
    from figma_flutter_agent.generator.subtree.merge import _rename_widget_class

    from .ast_helpers import _primary_public_widget_class_name
    from .paths import _is_large_planned_dart

    updated = dict(planned)
    for path, content in planned.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        expected = to_pascal_case(Path(path).stem)
        actual = _primary_public_widget_class_name(content)
        if actual is None:
            continue
        if actual == expected:
            continue
        if _is_large_planned_dart(content):
            logger.warning(
                "Skipping widget class rename in large file {} ({} vs {})",
                path,
                actual,
                expected,
            )
            continue
        updated[path] = _rename_widget_class(content, actual, expected)
        logger.info(
            "Aligned widget class {} -> {} in {}",
            actual,
            expected,
            path,
        )
    return updated


def _sync_widget_build_class_references(content: str, class_name: str) -> str:
    """Rewrite numbered alias ctor names in ``build`` to the declared widget class."""
    _MAX_WIDGET_ALIAS_SUFFIX_LEN = 2

    build_match = re.search(r"@override\s+Widget\s+build\s*\([^)]*\)", content)
    if build_match is None:
        build_match = re.search(r"Widget\s+build\s*\([^)]*\)", content)
    if build_match is None:
        return content
    start = build_match.end()
    body = content[start:]
    suffix_match = re.search(r"(\d+)$", class_name)
    if suffix_match:
        suffix = suffix_match.group(1)
        if len(suffix) > _MAX_WIDGET_ALIAS_SUFFIX_LEN:
            return content
        base = class_name[: suffix_match.start()]
        pattern = rf"\b{re.escape(base)}(?!{re.escape(suffix)})\s*\("
    else:
        pattern = rf"\b{re.escape(class_name)}\d+\s*\("
    patched = re.sub(pattern, f"{class_name}(", body)
    if patched == body:
        return content
    return content[:start] + patched

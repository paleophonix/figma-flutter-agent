"""Screen delegation to layout."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from loguru import logger

from .paths import _is_large_planned_dart, planned_content_for_path
from .shell import _screen_shell_block_for_fallback

_SCREEN_ARTBOARD_PREVIEW_IN_BUILD_RE = re.compile(
    r"class\s+(?!GeneratedScreenShell\b)\w+Screen\b[\s\S]*?"
    r"if\s*\(\s*_artboardPreview(?:Width|Height)\b",
    re.MULTILINE,
)
_INVALID_SCREEN_CLASS_NAME_RE = re.compile(r"\bclass\s+\d\w*")
_SCREEN_LAYOUT_POLLUTION_MARKERS = (
    "designWidth",
    "designHeight",
    "canvasWidth",
    "canvasHeight",
)
_SCREEN_CLASS_OPEN_RE = re.compile(
    r"(class\s+(?!GeneratedScreenShell\b)\w+Screen\s+extends\s+\w+\s*\{)"
)


def _screen_is_layout_delegate(screen_source: str) -> bool:
    if "Stack(" in screen_source or "Positioned(" in screen_source:
        return False
    return bool(re.search(r"const\s+\w+Layout\s*\(\s*\)", screen_source))


def _screen_needs_layout_delegate_fallback(screen_source: str) -> bool:
    """True when LLM screen code must be replaced with a layout delegate stub."""
    if _screen_is_layout_delegate(screen_source):
        return False
    if _INVALID_SCREEN_CLASS_NAME_RE.search(screen_source):
        return True
    if any(marker in screen_source for marker in _SCREEN_LAYOUT_POLLUTION_MARKERS):
        return True
    return _SCREEN_ARTBOARD_PREVIEW_IN_BUILD_RE.search(screen_source) is not None


def _generated_layout_path_for_feature(feature: str) -> str:
    return f"lib/generated/{feature}_layout.dart"


def _layout_source_for_feature(
    planned: Mapping[str, str],
    feature: str,
    *,
    project_dir: Path | None = None,
) -> str | None:
    """Return deterministic layout Dart for ``feature`` from planned files or disk."""
    layout_path = _generated_layout_path_for_feature(feature)
    located = planned_content_for_path(planned, layout_path)
    if located is not None:
        return located[1]
    if project_dir is not None:
        disk_path = project_dir / layout_path
        if disk_path.is_file():
            return disk_path.read_text(encoding="utf-8")
    return None


def _layout_delegate_available(
    planned: Mapping[str, str],
    feature: str,
    *,
    project_dir: Path | None = None,
) -> bool:
    """True when a non-trivial deterministic layout file exists for ``feature``."""
    layout_source = _layout_source_for_feature(
        planned,
        feature,
        project_dir=project_dir,
    )
    if not layout_source or not layout_source.strip():
        return False
    from figma_flutter_agent.generator.layout.common import to_pascal_case

    layout_class = f"{to_pascal_case(feature)}Layout"
    if f"class {layout_class}" not in layout_source:
        return False
    return "Widget build(BuildContext context)" in layout_source


def _inject_artboard_preview_fields_if_missing(source: str) -> str:
    """Inject _artboardPreview static fields into a screen class that references them.

    The LLM sometimes copies _artboardPreviewWidth/_artboardPreviewHeight from the
    GeneratedScreenShell template context into the screen class build() method. Those
    fields are only declared in GeneratedScreenShell, so the screen class gets an
    'undefined identifier' analyzer error. This function detects the pattern and
    injects the static field declarations into the screen class body.
    """
    from figma_flutter_agent.generator.layout.common import (
        ARTBOARD_PREVIEW_CLASS_FIELDS,
        ARTBOARD_PREVIEW_LAYOUT_MARKER,
    )

    if ARTBOARD_PREVIEW_LAYOUT_MARKER not in source:
        return source
    if "static final double _artboardPreviewWidth" in source:
        if source.count("static final double _artboardPreviewWidth") >= 2:
            return source
        match = _SCREEN_CLASS_OPEN_RE.search(source)
        if match is None:
            return source
        decl_idx = source.index("static final double _artboardPreviewWidth")
        if decl_idx > match.start():
            return source
    match = _SCREEN_CLASS_OPEN_RE.search(source)
    if match is None:
        return source
    insert_pos = match.end()
    return source[:insert_pos] + "\n" + ARTBOARD_PREVIEW_CLASS_FIELDS + source[insert_pos:]


def force_polluted_feature_screens_to_layout(
    planned: dict[str, str],
    *,
    package_name: str = "demo_app",
    responsive_enabled: bool = True,
    max_web_width: int = 1200,
    project_dir: Path | None = None,
) -> dict[str, str]:
    """Replace analyzer-poisoned feature screens with deterministic layout delegates."""
    replace_paths: list[str] = []
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/features/") or not normalized.endswith("_screen.dart"):
            continue
        if not _screen_needs_layout_delegate_fallback(content):
            continue
        feature = Path(normalized).parent.name
        if not _layout_delegate_available(
            planned,
            feature,
            project_dir=project_dir,
        ):
            continue
        replace_paths.append(normalized)
        logger.warning(
            "Replacing polluted {} with layout delegate (undefined layout tokens or invalid class name)",
            normalized,
        )
    if not replace_paths:
        return planned
    return fallback_unparseable_screens_to_layout(
        planned,
        tuple(replace_paths),
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        max_web_width=max_web_width,
    )


def force_oversized_feature_screens_to_layout(
    planned: dict[str, str],
    *,
    package_name: str = "demo_app",
    responsive_enabled: bool = True,
    max_web_width: int = 1200,
    max_screen_bytes: int | None = None,
) -> dict[str, str]:
    """Replace bloated feature screens with a layout delegate when layout codegen exists.

    IR/LLM materialization can inflate ``*_screen.dart`` to hundreds of KB while
    ``lib/generated/*_layout.dart`` already holds the deterministic UI. Keeping both
    duplicates slows ``dart format`` and breaks AST size limits.
    """
    from .paths import _LARGE_PLANNED_DART_BYTES

    byte_limit = max_screen_bytes if max_screen_bytes is not None else _LARGE_PLANNED_DART_BYTES
    replace_paths: list[str] = []
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/features/") or not normalized.endswith("_screen.dart"):
            continue
        if _screen_is_layout_delegate(content):
            continue
        if len(content.encode("utf-8")) <= byte_limit:
            continue
        feature = Path(normalized).parent.name
        if not _layout_delegate_available(planned, feature):
            continue
        replace_paths.append(normalized)
        logger.warning(
            "Replacing oversized {} ({} bytes) with layout delegate",
            normalized,
            len(content.encode("utf-8")),
        )
    if not replace_paths:
        return planned
    return fallback_unparseable_screens_to_layout(
        planned,
        tuple(replace_paths),
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        max_web_width=max_web_width,
    )


def split_oversized_layout_dart(
    layout_path: str,
    content: str,
    *,
    max_chunk_bytes: int | None = None,
) -> dict[str, str]:
    """Split an oversized layout file into shell + body chunks (INV-AST-COVERAGE)."""
    from .paths import _LARGE_PLANNED_DART_BYTES

    limit = max_chunk_bytes or _LARGE_PLANNED_DART_BYTES
    if len(content.encode("utf-8")) <= limit:
        return {layout_path: content}
    from figma_flutter_agent.tools.ast_sidecar.keys import discover_figma_node_ids

    base = layout_path.replace("_layout.dart", "")
    shell_path = f"{base}_shell.dart"
    node_ids = discover_figma_node_ids(content)
    if not node_ids:
        return {layout_path: content}
    chunks: dict[str, str] = {}
    header_end = content.find("class ")
    header = content[:header_end] if header_end > 0 else ""
    shell = (
        f"{header}"
        f"// Layout shell - body widgets extracted for chunked AST passes.\n"
        f"class _LayoutShell {{ const _LayoutShell(); }}\n"
    )
    chunks[shell_path] = shell
    for index, node_id in enumerate(node_ids):
        from figma_flutter_agent.tools.ast_sidecar import extract_widget_by_figma_id

        snippet = extract_widget_by_figma_id(content, node_id)
        if snippet is None:
            continue
        chunk_path = f"{base}_body_{index}.dart"
        chunks[chunk_path] = f"// figma chunk {node_id}\n{snippet}\n"
    if len(chunks) <= 1:
        return {layout_path: content}
    return chunks


def fallback_unparseable_screens_to_layout(
    planned: dict[str, str],
    format_paths: tuple[str, ...],
    *,
    package_name: str,
    responsive_enabled: bool = True,
    max_web_width: int = 1200,
) -> dict[str, str]:
    """Last-resort: delegate screen ``build`` to the deterministic layout widget."""
    if not format_paths:
        return planned
    from figma_flutter_agent.generator.dart.llm_codegen import _layout_delegation_screen_stub
    from figma_flutter_agent.parser.navigation import _screen_class_name

    layout_theme_import = f"package:{package_name}/theme/app_layout.dart"

    for path in format_paths:
        normalized = path.replace("\\", "/")
        if not normalized.endswith("_screen.dart"):
            continue
        feature = Path(normalized).parent.name
        screen_class = _screen_class_name(feature)
        layout_class = screen_class.replace("Screen", "Layout")
        layout_import = f"package:{package_name}/generated/{feature}_layout.dart"
        located = planned_content_for_path(planned, normalized)
        prior = located[1] if located is not None else ""
        custom_block = ""
        match = re.search(
            r"// <custom-code>\n(.*?)// </custom-code>",
            prior,
            flags=re.DOTALL,
        )
        if match is not None:
            custom_block = match.group(1)
        imports = [
            "import 'package:flutter/material.dart';",
            f"import '{layout_import}';",
        ]
        shell_block = ""
        if responsive_enabled:
            imports.insert(1, f"import '{layout_theme_import}';")
            shell_block = _screen_shell_block_for_fallback(max_web_width=max_web_width)
        screen_body = _layout_delegation_screen_stub(
            screen_class,
            layout_class,
            responsive_enabled=responsive_enabled,
        )
        stub = (
            "// <auto-generated>\n"
            "// Generated by figma-flutter-agent. Do not edit by hand.\n"
            "// </auto-generated>\n\n"
            + "\n".join(imports)
            + "\n\n"
            "// <custom-code>\n"
            f"{custom_block}"
            "// </custom-code>\n\n"
            f"{shell_block}"
            f"{screen_body}"
        )
        logger.warning(
            "Emit parse gate: replaced unparseable {} with layout delegate {}",
            normalized,
            layout_class,
        )
        planned[normalized] = stub
    return planned


def _apply_oversized_layout_splits(planned: dict[str, str]) -> dict[str, str]:
    """Split oversized layout files into shell/body chunks before AST reconcile."""
    updated = dict(planned)
    for path, content in list(planned.items()):
        normalized = path.replace("\\", "/")
        if not normalized.startswith("lib/generated/") or not normalized.endswith("_layout.dart"):
            continue
        if not _is_large_planned_dart(content):
            continue
        chunks = split_oversized_layout_dart(normalized, content)
        if len(chunks) <= 1:
            continue
        for chunk_path, chunk_content in chunks.items():
            updated[chunk_path] = chunk_content
        updated.pop(path, None)
    return updated


def refresh_shrunk_and_delegate_planned_widgets(
    planned: dict[str, str],
    *,
    clean_tree,
    widget_suffix: str,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    cluster_summary: dict[str, int] | None = None,
    cluster_min_count: int = 2,
    destination_trees: dict | None = None,
) -> dict[str, str]:
    """Re-render subtree/cluster widgets after shrink-only or foreign-delegate repair."""
    from figma_flutter_agent.generator.subtree import (
        build_cluster_render_context,
        collect_subtree_widget_specs,
        refresh_subtree_widget_planned_files,
    )
    from figma_flutter_agent.generator.subtree.plan import (
        _collect_subtree_specs_to_render,
        _layout_widget_class_names,
    )
    from figma_flutter_agent.generator.widget_extractor import (
        refresh_cluster_widget_planned_files,
    )

    from .class_inspect import consolidate_planned_widget_paths

    updated = dict(planned)
    if cluster_summary:
        updated = refresh_cluster_widget_planned_files(
            updated,
            clean_tree=clean_tree,
            cluster_summary=cluster_summary,
            min_count=cluster_min_count,
            widget_suffix=widget_suffix,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            destination_trees=destination_trees,
        )
        updated = consolidate_planned_widget_paths(updated)
    specs = list(collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix))
    if not specs:
        return updated
    layout_names = sorted(_layout_widget_class_names(updated))
    cluster_classes: dict[str, str] | None = None
    cluster_vector_variants: dict | None = None
    if cluster_summary:
        cluster_classes, cluster_vector_variants = build_cluster_render_context(
            clean_tree,
            cluster_summary=cluster_summary,
            widget_suffix=widget_suffix,
            min_count=cluster_min_count,
            destination_trees=destination_trees,
        )
    if not _collect_subtree_specs_to_render(
        updated,
        specs,
        layout_class_names=layout_names,
        clean_tree=clean_tree,
    ):
        return updated
    return refresh_subtree_widget_planned_files(
        updated,
        clean_tree=clean_tree,
        widget_suffix=widget_suffix,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )

"""Deterministic widgets for vector-rich screen subtrees in LLM generation mode."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.generator.layout.renderer import render_node_body, render_widget_file
from figma_flutter_agent.generator.renderer import to_pascal_case, to_snake_case
from figma_flutter_agent.parser.interaction import (
    looks_like_media_controls_stack,
    looks_like_password_field_stack,
    stack_interaction_kind,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, FlutterGenerationResponse, NodeType

_MIN_VECTOR_NODES = 8
_MIN_SUBTREE_AREA = 12_000.0
_MIN_COMPACT_ICON_VECTORS = 2
_MAX_COMPACT_ICON_VECTORS = 12
_MAX_COMPACT_ICON_WIDTH = 64.0
_MAX_COMPACT_ICON_HEIGHT = 64.0
_GEOMETRY_SOCIAL_ROW_CONFIDENCE = 0.7
_INTERACTIVE_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.TEXT,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
    }
)
_WIDGET_CLASS_RE = re.compile(
    r"class\s+(?P<name>\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)
_SVG_ASSET_PATH_RE = re.compile(r"SvgPicture\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")
_IMAGE_ASSET_PATH_RE = re.compile(r"Image\.asset\(\s*['\"](?P<path>assets/[^'\"]+)['\"]")
_POSITIONED_CALL_RE = re.compile(r"(?<![A-Za-z0-9_])Positioned\(")
_WIDGET_CLASS_DECL_RE = re.compile(
    r"(?:^|\n)class\s+\w+\s+extends\s+(?:StatelessWidget|StatefulWidget)\b"
)
_LAYOUT_WIDGET_REF_RE = re.compile(r"const\s+(\w+Widget\d*)\s*\(")


@dataclass(frozen=True)
class SubtreeWidgetSpec:
    """Metadata for a deterministic subtree-backed widget."""

    node_id: str
    class_name: str
    file_name: str
    representative: CleanDesignTreeNode
    vector_count: int


@dataclass(frozen=True)
class SubtreeWidgetResult:
    """Generated subtree widget files."""

    files: dict[str, str]
    specs: tuple[SubtreeWidgetSpec, ...]


def _count_vector_nodes(node: CleanDesignTreeNode) -> int:
    total = 0
    if node.type in {NodeType.VECTOR, NodeType.IMAGE} or node.vector_asset_key or node.image_asset_key:
        total += 1
    for child in node.children:
        total += _count_vector_nodes(child)
    return total


def _count_interactive_nodes(node: CleanDesignTreeNode) -> int:
    total = 1 if node.type in _INTERACTIVE_TYPES else 0
    for child in node.children:
        total += _count_interactive_nodes(child)
    return total


def _subtree_area(node: CleanDesignTreeNode) -> float:
    width = node.sizing.width or 0.0
    height = node.sizing.height or 0.0
    return width * height


def _subtree_class_name(node: CleanDesignTreeNode, widget_suffix: str) -> str:
    base = to_pascal_case(node.name) or f"Subtree{node.id.replace(':', '')}"
    if base.endswith(widget_suffix):
        return base
    return f"{base}{widget_suffix}"


def _is_subtree_candidate(node: CleanDesignTreeNode, *, is_direct_child: bool = False) -> bool:
    if node.render_boundary:
        return False
    if node.vector_asset_key and not node.children:
        return False
    vector_count = _count_vector_nodes(node)
    min_vectors = 6 if is_direct_child else _MIN_VECTOR_NODES
    if vector_count < min_vectors:
        return False
    if not is_direct_child and _subtree_area(node) < _MIN_SUBTREE_AREA:
        return False
    interactive_count = _count_interactive_nodes(node)
    return vector_count > interactive_count


def _is_compact_icon_subtree(node: CleanDesignTreeNode) -> bool:
    """Detect small multicolor icon stacks (e.g. Google G) that LLMs often break."""
    if node.type != NodeType.STACK:
        return False
    vector_count = _count_vector_nodes(node)
    if vector_count < _MIN_COMPACT_ICON_VECTORS or vector_count > _MAX_COMPACT_ICON_VECTORS:
        return False
    placement = node.stack_placement
    if placement is None or placement.width is None or placement.height is None:
        return False
    if placement.width > _MAX_COMPACT_ICON_WIDTH or placement.height > _MAX_COMPACT_ICON_HEIGHT:
        return False
    return _count_interactive_nodes(node) < vector_count


def _with_screen_stack_placement(
    node: CleanDesignTreeNode,
    *,
    screen_left: float,
    screen_top: float,
) -> CleanDesignTreeNode:
    placement = node.stack_placement
    if placement is None:
        return node
    return node.model_copy(
        update={
            "stack_placement": placement.model_copy(
                update={"left": screen_left, "top": screen_top},
            ),
        },
    )


def _append_subtree_spec_from_ref(
    specs: list[SubtreeWidgetSpec],
    *,
    node: CleanDesignTreeNode,
    class_name: str,
    used_file_names: set[str],
    used_class_names: set[str],
    used_node_ids: set[str],
) -> None:
    """Register a subtree widget already replaced by ``extracted_widget_ref`` on the tree."""
    if node.id in used_node_ids:
        return
    resolved_class = class_name
    file_name = to_snake_case(resolved_class)
    suffix = 2
    while file_name in used_file_names or resolved_class in used_class_names:
        resolved_class = f"{class_name}{suffix}"
        file_name = to_snake_case(resolved_class)
        suffix += 1
    used_file_names.add(file_name)
    used_class_names.add(resolved_class)
    used_node_ids.add(node.id)
    specs.append(
        SubtreeWidgetSpec(
            node_id=node.id,
            class_name=resolved_class,
            file_name=file_name,
            representative=node,
            vector_count=_count_vector_nodes(node),
        )
    )


def _append_subtree_spec(
    specs: list[SubtreeWidgetSpec],
    *,
    node: CleanDesignTreeNode,
    widget_suffix: str,
    used_file_names: set[str],
    used_class_names: set[str],
    used_node_ids: set[str],
    screen_left: float | None = None,
    screen_top: float | None = None,
) -> None:
    if node.id in used_node_ids:
        return
    representative = node
    if screen_left is not None and screen_top is not None:
        representative = _with_screen_stack_placement(
            node,
            screen_left=screen_left,
            screen_top=screen_top,
        )
    base_class_name = _subtree_class_name(node, widget_suffix)
    class_name = base_class_name
    file_name = to_snake_case(class_name)
    suffix = 2
    while file_name in used_file_names or class_name in used_class_names:
        class_name = f"{base_class_name}{suffix}"
        file_name = to_snake_case(class_name)
        suffix += 1
    used_file_names.add(file_name)
    used_class_names.add(class_name)
    used_node_ids.add(node.id)
    specs.append(
        SubtreeWidgetSpec(
            node_id=node.id,
            class_name=class_name,
            file_name=file_name,
            representative=representative,
            vector_count=_count_vector_nodes(node),
        )
    )


def _social_button_subtree_ids(root: CleanDesignTreeNode) -> frozenset[str]:
    """Node ids inside auth buttons and geometry-detected social rows (icons stay in-button)."""
    from figma_flutter_agent.parser.geometry import auth_button_confidence

    ids: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        ids.add(node.id)
        for child in node.children:
            walk(child)

    for node in _collect_all_nodes(root):
        if node.type == NodeType.BUTTON and auth_button_confidence(node) >= _GEOMETRY_SOCIAL_ROW_CONFIDENCE:
            walk(node)
    for stack in _collect_social_auth_button_stacks(root):
        walk(stack)
    return frozenset(ids)


def _walk_compact_icon_subtrees(
    node: CleanDesignTreeNode,
    *,
    offset_left: float,
    offset_top: float,
    widget_suffix: str,
    specs: list[SubtreeWidgetSpec],
    used_file_names: set[str],
    used_class_names: set[str],
    used_node_ids: set[str],
    excluded_node_ids: frozenset[str],
) -> None:
    from figma_flutter_agent.assets.composite_icons import is_composite_icon_export_node

    if is_composite_icon_export_node(node):
        return
    if node.id in excluded_node_ids:
        return
    ref = (node.extracted_widget_ref or "").strip()
    if ref:
        _append_subtree_spec_from_ref(
            specs,
            node=node,
            class_name=ref,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
        )
        return
    placement = node.stack_placement
    screen_left = offset_left + (placement.left if placement is not None else 0.0)
    screen_top = offset_top + (placement.top if placement is not None else 0.0)
    if _is_compact_icon_subtree(node):
        _append_subtree_spec(
            specs,
            node=node,
            widget_suffix=widget_suffix,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
            screen_left=screen_left,
            screen_top=screen_top,
        )
    for child in node.children:
        _walk_compact_icon_subtrees(
            child,
            offset_left=screen_left,
            offset_top=screen_top,
            widget_suffix=widget_suffix,
            specs=specs,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
            excluded_node_ids=excluded_node_ids,
        )


def collect_subtree_widget_specs(
    root: CleanDesignTreeNode,
    *,
    widget_suffix: str,
    reserved_file_names: set[str] | None = None,
) -> list[SubtreeWidgetSpec]:
    """Collect vector-rich direct child subtrees that should not be simplified by the LLM."""
    reserved = reserved_file_names or set()
    specs: list[SubtreeWidgetSpec] = []
    used_file_names = set(reserved)
    used_class_names: set[str] = set()
    used_node_ids: set[str] = set()

    social_ids = _social_button_subtree_ids(root)
    for child in root.children:
        ref = (child.extracted_widget_ref or "").strip()
        if ref:
            _append_subtree_spec_from_ref(
                specs,
                node=child,
                class_name=ref,
                used_file_names=used_file_names,
                used_class_names=used_class_names,
                used_node_ids=used_node_ids,
            )
            continue
        if child.id in social_ids:
            continue
        if (
            stack_interaction_kind(child) == "input"
            or looks_like_password_field_stack(child)
            or looks_like_media_controls_stack(child)
        ):
            continue
        if not _is_subtree_candidate(child, is_direct_child=True):
            continue
        _append_subtree_spec(
            specs,
            node=child,
            widget_suffix=widget_suffix,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
        )

    excluded = social_ids | frozenset(used_node_ids)
    for child in root.children:
        if child.id in excluded:
            continue
        _walk_compact_icon_subtrees(
            child,
            offset_left=0.0,
            offset_top=0.0,
            widget_suffix=widget_suffix,
            specs=specs,
            used_file_names=used_file_names,
            used_class_names=used_class_names,
            used_node_ids=used_node_ids,
            excluded_node_ids=excluded,
        )
    return [spec for spec in specs if spec.node_id not in social_ids]


_LARGE_TRUSTED_SUBTREE_WIDGET_BYTES = 200_000
_MIN_BOTTOM_NAV_BAR_ITEMS = 2


def _bottom_nav_widget_needs_refresh(source: str) -> bool:
    """True when a cached bottom-nav widget file has too few tab items."""
    if "_LayoutChromeNav(" not in source:
        return False
    return source.count("BottomNavigationBarItem(") < _MIN_BOTTOM_NAV_BAR_ITEMS


def _subtree_widget_path_needs_render(
    planned: Mapping[str, str],
    class_name: str,
) -> bool:
    from figma_flutter_agent.generator.planned.reconcile import (
        _is_foreign_delegate_widget_build,
        _is_self_referential_widget_build,
        _is_shrink_only_widget_source,
        preferred_widget_path_for_class,
    )

    preferred = preferred_widget_path_for_class(class_name)
    existing = (planned.get(preferred) or "").strip()
    if not existing:
        return True
    if _bottom_nav_widget_needs_refresh(existing):
        return True
    if len(existing.encode("utf-8")) > _LARGE_TRUSTED_SUBTREE_WIDGET_BYTES:
        if not _is_shrink_only_widget_source(existing) and not _is_self_referential_widget_build(
            existing, class_name
        ) and not _is_foreign_delegate_widget_build(existing, class_name):
            return False
    if _is_shrink_only_widget_source(existing):
        return True
    if _is_self_referential_widget_build(existing, class_name):
        return True
    return _is_foreign_delegate_widget_build(existing, class_name)


def _collect_subtree_specs_to_render(
    planned: Mapping[str, str],
    specs: Sequence[SubtreeWidgetSpec],
    *,
    layout_class_names: Sequence[str] = (),
    clean_tree: CleanDesignTreeNode | None = None,
) -> list[SubtreeWidgetSpec]:
    """Subtree specs whose planned widget file is missing, shrink-only, or self-referential."""
    to_render: list[SubtreeWidgetSpec] = []
    seen_node_ids: set[str] = set()

    def _maybe_add(spec: SubtreeWidgetSpec) -> None:
        if spec.node_id in seen_node_ids:
            return
        if not _subtree_widget_path_needs_render(planned, spec.class_name):
            return
        seen_node_ids.add(spec.node_id)
        to_render.append(spec)

    for spec in specs:
        _maybe_add(spec)

    if clean_tree is not None:
        for class_name in layout_class_names:
            if not _subtree_widget_path_needs_render(planned, class_name):
                continue
            resolved = _resolve_spec_for_layout_widget_class(
                class_name,
                list(specs),
                clean_tree=clean_tree,
            )
            if resolved is not None:
                _maybe_add(resolved)

    return to_render


def seed_subtree_widgets_from_project(
    planned: dict[str, str],
    *,
    project_dir: Path | None,
    specs: Sequence[SubtreeWidgetSpec],
) -> dict[str, str]:
    """Copy valid on-disk subtree widgets into ``planned`` before re-rendering."""
    if project_dir is None or not project_dir.is_dir() or not specs:
        return planned
    from figma_flutter_agent.generator.planned.reconcile import preferred_widget_path_for_class

    merged = dict(planned)
    for spec in specs:
        if not _subtree_widget_path_needs_render(merged, spec.class_name):
            continue
        rel = preferred_widget_path_for_class(spec.class_name)
        disk = project_dir / rel
        if not disk.is_file():
            continue
        body = disk.read_text(encoding="utf-8")
        if _subtree_widget_path_needs_render({rel: body}, spec.class_name):
            continue
        merged[rel] = body
        logger.info("Seeded subtree widget {} from project disk", spec.class_name)
    return merged


def plan_subtree_widget_files(
    planned: dict[str, str],
    specs: Sequence[SubtreeWidgetSpec],
    *,
    project_dir: Path | None,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
    clean_tree: CleanDesignTreeNode | None = None,
) -> tuple[dict[str, str], SubtreeWidgetResult | None]:
    """Seed widgets from disk when possible; render only missing or broken bodies."""
    if not specs:
        return planned, None
    from figma_flutter_agent.generator.planned.reconcile import (
        preferred_widget_path_for_class,
        repair_foreign_delegate_widget_builds,
        repair_stale_widget_ctor_names_in_planned,
    )

    merged = repair_foreign_delegate_widget_builds(dict(planned))
    merged = repair_stale_widget_ctor_names_in_planned(merged)
    merged = seed_subtree_widgets_from_project(
        merged,
        project_dir=project_dir,
        specs=specs,
    )
    logger.info("Subtree plan: checking {} widget spec(s)", len(specs))
    layout_names = (
        sorted(_layout_widget_class_names(merged)) if clean_tree is not None else ()
    )
    to_render = _collect_subtree_specs_to_render(
        merged,
        specs,
        layout_class_names=layout_names,
        clean_tree=clean_tree,
    )
    logger.info("Subtree plan: {} widget(s) need render", len(to_render))
    if not to_render:
        files: dict[str, str] = {}
        for spec in specs:
            preferred = preferred_widget_path_for_class(spec.class_name)
            legacy = f"lib/widgets/{spec.file_name}.dart"
            content = merged.get(preferred) or merged.get(legacy)
            if content is not None:
                files[legacy] = content
        return merged, SubtreeWidgetResult(files=files, specs=tuple(specs))

    started = time.monotonic()
    logger.info("Rendering {} subtree widget(s)...", len(to_render))
    subtree = render_subtree_widgets(
        to_render,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )
    logger.info(
        "Subtree widgets rendered in {:.1f}s ({} skipped as already valid)",
        time.monotonic() - started,
        len(specs) - len(to_render),
    )
    for spec in to_render:
        legacy_path = f"lib/widgets/{spec.file_name}.dart"
        content = subtree.files.get(legacy_path)
        if content is not None:
            merged[preferred_widget_path_for_class(spec.class_name)] = content
    return merged, subtree


def ensure_subtree_widget_planned_files(
    planned: dict[str, str],
    *,
    clean_tree: CleanDesignTreeNode,
    widget_suffix: str,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
) -> dict[str, str]:
    """Render missing ``lib/widgets`` files required by layout ``extracted_widget_ref`` stubs."""
    specs = collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
    if not specs:
        return planned
    merged = dict(planned)
    to_render = _collect_subtree_specs_to_render(merged, specs)
    if not to_render:
        return merged
    started = time.monotonic()
    subtree = render_subtree_widgets(
        to_render,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
    )
    from figma_flutter_agent.generator.planned.reconcile import preferred_widget_path_for_class

    for spec in to_render:
        legacy_path = f"lib/widgets/{spec.file_name}.dart"
        content = subtree.files.get(legacy_path)
        if content is None:
            continue
        merged[preferred_widget_path_for_class(spec.class_name)] = content
    logger.info(
        "Rendered {} missing subtree widget(s) in {:.1f}s ({} already present)",
        len(to_render),
        time.monotonic() - started,
        len(specs) - len(to_render),
    )
    return merged


def _layout_widget_class_names(planned: Mapping[str, str]) -> set[str]:
    names: set[str] = set()
    for path, content in planned.items():
        normalized = path.replace("\\", "/")
        if not normalized.endswith("_layout.dart"):
            continue
        names.update(_LAYOUT_WIDGET_REF_RE.findall(content))
    return names


def _resolve_spec_for_layout_widget_class(
    class_name: str,
    specs: Sequence[SubtreeWidgetSpec],
    *,
    clean_tree: CleanDesignTreeNode,
) -> SubtreeWidgetSpec | None:
    direct = next((spec for spec in specs if spec.class_name == class_name), None)
    if direct is not None:
        return direct

    ref_node_ids = {
        node.id
        for node in _collect_all_nodes(clean_tree)
        if (node.extracted_widget_ref or "").strip() == class_name
    }
    if ref_node_ids:
        matched = next((spec for spec in specs if spec.node_id in ref_node_ids), None)
        if matched is not None:
            return matched

    from figma_flutter_agent.generator.layout.common import to_snake_case
    from figma_flutter_agent.generator.planned.reconcile import _normalized_widget_stem

    target_stem = _normalized_widget_stem(to_snake_case(class_name))
    stem_matches = [
        spec
        for spec in specs
        if _normalized_widget_stem(to_snake_case(spec.class_name)) == target_stem
    ]
    if len(stem_matches) == 1:
        spec = stem_matches[0]
        if spec.class_name == class_name:
            return spec
        return SubtreeWidgetSpec(
            node_id=spec.node_id,
            class_name=class_name,
            file_name=to_snake_case(class_name),
            representative=spec.representative,
            vector_count=spec.vector_count,
        )

    base = re.sub(r"\d+$", "", class_name)
    if not base:
        return None
    prefix_matches = [spec for spec in specs if spec.class_name.startswith(base)]
    if len(prefix_matches) != 1:
        return None
    spec = prefix_matches[0]
    if spec.class_name == class_name:
        return spec
    return SubtreeWidgetSpec(
        node_id=spec.node_id,
        class_name=class_name,
        file_name=to_snake_case(class_name),
        representative=spec.representative,
        vector_count=spec.vector_count,
    )


def build_cluster_render_context(
    clean_tree: CleanDesignTreeNode,
    *,
    cluster_summary: dict[str, int],
    widget_suffix: str = "Widget",
    min_count: int = 2,
    destination_trees: dict[str, CleanDesignTreeNode] | None = None,
) -> tuple[dict[str, str] | None, dict | None]:
    """Build ``cluster_classes`` / ``cluster_vector_variants`` for subtree and layout render."""
    from figma_flutter_agent.generator.cluster_variants import (
        collect_cluster_vector_variants,
        restore_pruned_cluster_vector_keys,
    )
    from figma_flutter_agent.generator.widget_extractor import collect_cluster_widget_specs

    cluster_specs = collect_cluster_widget_specs(
        clean_tree,
        cluster_summary,
        min_count=min_count,
        widget_suffix=widget_suffix,
    )
    if not cluster_specs:
        return None, None
    cluster_classes = {spec.cluster_id: spec.class_name for spec in cluster_specs}
    subtree_specs = collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
    variant_trees: list[CleanDesignTreeNode] = [clean_tree]
    if destination_trees:
        variant_trees.extend(destination_trees.values())
    variant_trees.extend(_prepare_subtree_render_root(spec.representative) for spec in subtree_specs)
    cluster_vector_variants = collect_cluster_vector_variants(
        variant_trees,
        {spec.cluster_id: spec.representative for spec in cluster_specs},
    )
    restore_pruned_cluster_vector_keys(clean_tree, cluster_vector_variants)
    if destination_trees:
        for destination_tree in destination_trees.values():
            restore_pruned_cluster_vector_keys(destination_tree, cluster_vector_variants)
    return cluster_classes, cluster_vector_variants


def refresh_subtree_widget_planned_files(
    planned: dict[str, str],
    *,
    clean_tree: CleanDesignTreeNode,
    widget_suffix: str,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
) -> dict[str, str]:
    """Re-render subtree widgets when planned bodies are shrink stubs or self-referential."""
    from figma_flutter_agent.generator.planned.reconcile import (
        _is_foreign_delegate_widget_build,
        _is_self_referential_widget_build,
        _is_shrink_only_widget_source,
        preferred_widget_path_for_class,
    )

    specs = list(collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix))
    if not specs:
        return planned

    merged = dict(planned)
    layout_names = sorted(_layout_widget_class_names(planned))
    to_render = _collect_subtree_specs_to_render(
        merged,
        specs,
        layout_class_names=layout_names,
        clean_tree=clean_tree,
    )
    if not to_render:
        return merged

    started = time.monotonic()
    subtree = render_subtree_widgets(
        to_render,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )
    logger.info(
        "Refreshed {} subtree widget(s) in {:.1f}s (skipped {} valid)",
        len(to_render),
        time.monotonic() - started,
        len(specs) + len(layout_names) - len(to_render),
    )

    def _should_refresh(path: str, class_name: str) -> bool:
        existing = merged.get(path, "")
        if not existing:
            return True
        if _bottom_nav_widget_needs_refresh(existing):
            return True
        if _is_shrink_only_widget_source(existing):
            return True
        if _is_self_referential_widget_build(existing, class_name):
            return True
        return _is_foreign_delegate_widget_build(existing, class_name)

    def _apply_fresh(spec: SubtreeWidgetSpec, fresh: str) -> None:
        preferred = preferred_widget_path_for_class(spec.class_name)
        if _should_refresh(preferred, spec.class_name):
            merged[preferred] = fresh

    for spec in to_render:
        legacy_path = f"lib/widgets/{spec.file_name}.dart"
        preferred = preferred_widget_path_for_class(spec.class_name)
        fresh = subtree.files.get(legacy_path) or subtree.files.get(preferred)
        if fresh is None:
            continue
        _apply_fresh(spec, fresh)

    for class_name in layout_names:
        preferred = preferred_widget_path_for_class(class_name)
        if not _should_refresh(preferred, class_name):
            continue
        spec = _resolve_spec_for_layout_widget_class(
            class_name,
            specs,
            clean_tree=clean_tree,
        )
        if spec is None:
            continue
        if spec.class_name == class_name:
            legacy_path = f"lib/widgets/{spec.file_name}.dart"
            fresh = subtree.files.get(legacy_path) or subtree.files.get(preferred)
            if fresh is None:
                origin = next((item for item in specs if item.node_id == spec.node_id), None)
                if origin is not None:
                    origin_path = f"lib/widgets/{origin.file_name}.dart"
                    fresh = subtree.files.get(origin_path) or subtree.files.get(
                        preferred_widget_path_for_class(origin.class_name)
                    )
            if fresh is None or spec.class_name not in fresh:
                body = _render_subtree_widget_body(
                    spec.representative,
                    class_name=spec.class_name,
                    uses_svg=uses_svg,
                    cluster_classes=cluster_classes,
                    cluster_vector_variants=cluster_vector_variants,
                )
                fresh = render_widget_file(
                    class_name=spec.class_name,
                    body=body,
                    uses_svg=uses_svg,
                    package_name=package_name,
                    use_package_imports=use_package_imports,
                    source_file=preferred,
                )
            _apply_fresh(spec, fresh)
            continue
        body = _render_subtree_widget_body(
            spec.representative,
            class_name=spec.class_name,
            uses_svg=uses_svg,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
        )
        fresh = render_widget_file(
            class_name=spec.class_name,
            body=body,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            source_file=preferred,
        )
        _apply_fresh(spec, fresh)

    return merged


def preserve_deterministic_widget_planned_files(
    planned: dict[str, str],
    baseline: dict[str, str],
) -> dict[str, str]:
    """Keep ``lib/widgets/*.dart`` from an earlier plan pass after IR re-plan drops them."""
    merged = dict(planned)
    for path, content in baseline.items():
        key = path.replace("\\", "/")
        if key.startswith("lib/widgets/") and key.endswith(".dart") and key not in merged:
            merged[key] = content
    return merged


def sync_subtree_extracted_widgets(
    generation: FlutterGenerationResponse,
    *,
    clean_tree: CleanDesignTreeNode,
    planned_files: dict[str, str],
    widget_suffix: str,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
) -> tuple[FlutterGenerationResponse, dict[str, str], bool]:
    """Ensure deterministic subtree widget files and ``extractedWidgets`` entries exist."""
    from figma_flutter_agent.schemas import ExtractedWidget

    specs = collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
    if not specs:
        return generation, planned_files, False

    subtree = render_subtree_widgets(
        specs,
        uses_svg=uses_svg,
        package_name=package_name,
        use_package_imports=use_package_imports,
    )
    merged_planned = dict(planned_files)
    changed = False
    for path, content in subtree.files.items():
        key = path.replace("\\", "/")
        if merged_planned.get(key) != content:
            merged_planned[key] = content
            changed = True

    by_name = {widget.widget_name: widget for widget in generation.extracted_widgets}
    widgets = list(generation.extracted_widgets)
    for spec in specs:
        path = f"lib/widgets/{spec.file_name}.dart"
        code = subtree.files.get(path)
        if not code:
            continue
        existing = by_name.get(spec.class_name)
        if existing is None:
            widgets.append(
                ExtractedWidget(
                    widget_name=spec.class_name,
                    code=code,
                ),
            )
            changed = True
            continue
        if not existing.resolved_code():
            idx = widgets.index(existing)
            widgets[idx] = existing.model_copy(update={"code": code})
            changed = True

    if not changed:
        return generation, merged_planned, False
    return generation.model_copy(update={"extracted_widgets": widgets}), merged_planned, True


def _subtree_render_root(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Strip placement stubs so subtree widget files render full bodies."""
    if not node.extracted_widget_ref:
        return node
    return node.model_copy(update={"extracted_widget_ref": None})


def _prepare_subtree_render_root(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Clone a subtree representative and apply the same cluster pruning as layout codegen."""
    from copy import deepcopy

    from figma_flutter_agent.parser.dedup import prune_duplicated_cluster_subtrees

    root = deepcopy(_subtree_render_root(node))
    prune_duplicated_cluster_subtrees(root)
    return root


def _subtree_skip_cluster_id_for_root(
    root: CleanDesignTreeNode,
    *,
    class_name: str,
    cluster_classes: dict[str, str] | None,
    cluster_vector_variants: dict | None = None,
) -> str | None:
    """Skip cluster shortcut on the subtree root when the file name differs from the cluster widget."""
    from figma_flutter_agent.generator.layout.widgets.render import _sizing_like_skip_control

    cluster_id = root.cluster_id
    if not cluster_id or not cluster_classes:
        return None
    mapped = cluster_classes.get(cluster_id)
    if not mapped or mapped == class_name:
        return None
    if not root.children and _sizing_like_skip_control(root):
        variant = cluster_vector_variants.get(cluster_id) if cluster_vector_variants else None
        if root.vector_asset_key or variant is not None:
            return None
    return cluster_id


def _render_subtree_widget_body(
    representative: CleanDesignTreeNode,
    *,
    class_name: str,
    uses_svg: bool,
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
) -> str:
    """Render a dedicated subtree widget file (inline cluster body, no sibling delegate)."""
    root = _prepare_subtree_render_root(representative)
    if root.type == NodeType.BOTTOM_NAV:
        from figma_flutter_agent.generator.layout.navigation import render_bottom_navigation

        return render_bottom_navigation(root, uses_svg=uses_svg)
    skip_cluster_id = _subtree_skip_cluster_id_for_root(
        root,
        class_name=class_name,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )
    return render_node_body(
        root,
        uses_svg=uses_svg,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
        skip_cluster_id=skip_cluster_id,
    )


def render_subtree_widgets(
    specs: list[SubtreeWidgetSpec],
    *,
    uses_svg: bool,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
    cluster_classes: dict[str, str] | None = None,
    cluster_vector_variants: dict | None = None,
) -> SubtreeWidgetResult:
    """Render deterministic widget files for vector-rich subtrees."""
    files: dict[str, str] = {}
    for spec in specs:
        body = _render_subtree_widget_body(
            spec.representative,
            class_name=spec.class_name,
            uses_svg=uses_svg,
            cluster_classes=cluster_classes,
            cluster_vector_variants=cluster_vector_variants,
        )
        path = f"lib/widgets/{spec.file_name}.dart"
        files[path] = render_widget_file(
            class_name=spec.class_name,
            body=body,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            source_file=path,
        )
    return SubtreeWidgetResult(files=files, specs=tuple(specs))


def replace_extracted_subtree_nodes_with_refs(
    root: CleanDesignTreeNode,
    specs: Sequence[SubtreeWidgetSpec],
) -> None:
    """Swap extracted subtree roots for placement stubs consumed by layout codegen."""
    by_id = {spec.node_id: spec.class_name for spec in specs}
    if not by_id:
        return

    def stub_for(node: CleanDesignTreeNode, class_name: str) -> CleanDesignTreeNode:
        return node.model_copy(update={"extracted_widget_ref": class_name})

    def walk(node: CleanDesignTreeNode) -> None:
        kept: list[CleanDesignTreeNode] = []
        for child in node.children:
            class_name = by_id.get(child.id)
            if class_name is not None:
                kept.append(stub_for(child, class_name))
                continue
            walk(child)
            kept.append(child)
        node.children = kept

    walk(root)


def build_subtree_widget_hints(specs: list[SubtreeWidgetSpec]) -> list[str]:
    """Build LLM hints for pre-rendered subtree widgets."""
    hints: list[str] = []
    for spec in specs:
        placement = spec.representative.stack_placement
        placement_hint = ""
        if (
            placement is not None
            and placement.width is not None
            and placement.height is not None
        ):
            placement_hint = (
                f" Place exactly one Positioned(left: {placement.left}, top: {placement.top}, "
                f"width: {placement.width}, height: {placement.height}, "
                f"child: const {spec.class_name}()) in screenCode."
            )
        hints.append(
            f"Prebuilt vector-rich subtree widget '{spec.class_name}' "
            f"(node {spec.node_id}, {spec.vector_count} vectors) is already generated at "
            f"lib/widgets/{spec.file_name}.dart.{placement_hint} "
            f"Use only `const {spec.class_name}()` for this subtree — do NOT inline SvgPicture "
            "stacks, abbreviate vector layers, redeclare the widget class in screenCode, or "
            "emit SizedBox.shrink() placeholder classes."
        )
    return hints


def _extract_asset_paths(source: str) -> frozenset[str]:
    paths = {match.group("path") for match in _SVG_ASSET_PATH_RE.finditer(source)}
    paths.update(match.group("path") for match in _IMAGE_ASSET_PATH_RE.finditer(source))
    return frozenset(paths)


def _primary_public_widget_class_name(source: str) -> str | None:
    """Return the exported widget class, ignoring private layout helper widgets."""
    public_names = [
        match.group("name")
        for match in _WIDGET_CLASS_RE.finditer(source)
        if not match.group("name").startswith("_")
    ]
    if not public_names:
        return None
    widget_names = [name for name in public_names if name.endswith("Widget")]
    if widget_names:
        return widget_names[-1]
    return public_names[-1]


def _extract_widget_class_name(source: str) -> str | None:
    return _primary_public_widget_class_name(source)


def _rename_widget_class(source: str, old_class: str, new_class: str) -> str:
    """Rename a widget class without rewriting sibling references inside ``build``."""
    if old_class == new_class:
        return source
    class_match = re.search(
        rf"class\s+{re.escape(old_class)}\s+extends\s+(?:StatelessWidget|StatefulWidget)\b",
        source,
    )
    if class_match is None:
        return re.sub(rf"\b{re.escape(old_class)}\b", new_class, source)
    build_match = re.search(
        r"@override\s+Widget\s+build\s*\(",
        source[class_match.end() :],
    )
    if build_match is None:
        return re.sub(rf"\b{re.escape(old_class)}\b", new_class, source)
    header_end = class_match.end() + build_match.start()
    header = source[:header_end]
    body = source[header_end:]
    return re.sub(rf"\b{re.escape(old_class)}\b", new_class, header) + body


def _collect_widget_class_names(
    planned_files: dict[str, str],
    *,
    exclude_paths: frozenset[str] | None = None,
) -> set[str]:
    excluded = exclude_paths or frozenset()
    names: set[str] = set()
    for path, content in planned_files.items():
        if path in excluded:
            continue
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        class_name = _extract_widget_class_name(content)
        if class_name is not None:
            names.add(class_name)
    return names


def _resolve_merged_widget_class_name(
    *,
    llm_class: str,
    subtree_class: str,
    spec_class: str | None,
    used_class_names: set[str],
) -> str:
    for candidate in (llm_class, spec_class or "", subtree_class):
        if candidate and candidate not in used_class_names:
            return candidate
    base = spec_class or llm_class or subtree_class
    suffix = 2
    while f"{base}{suffix}" in used_class_names:
        suffix += 1
    return f"{base}{suffix}"


def merge_thin_llm_widgets_with_subtrees(
    planned_files: dict[str, str],
    subtree_result: SubtreeWidgetResult,
) -> dict[str, str]:
    """Replace under-specified LLM extracted widgets with deterministic subtree bodies."""
    if not subtree_result.files:
        return planned_files

    updated = dict(planned_files)
    spec_by_path = {f"lib/widgets/{spec.file_name}.dart": spec for spec in subtree_result.specs}
    subtree_assets = {
        path: _extract_asset_paths(content) for path, content in subtree_result.files.items()
    }

    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    for path, llm_content in list(updated.items()):
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue

        llm_assets = _extract_asset_paths(llm_content)
        llm_syntax_broken = validate_dart_delimiters(llm_content) is not None
        if not llm_assets:
            continue

        best_path: str | None = None
        best_score = 0.0
        best_assets: frozenset[str] = frozenset()
        for subtree_path, assets in subtree_assets.items():
            if not assets:
                continue
            overlap = len(llm_assets & assets)
            if overlap == 0:
                continue
            score = overlap / len(llm_assets)
            if score > best_score:
                best_score = score
                best_path = subtree_path
                best_assets = assets

        if llm_syntax_broken and best_path is None:
            stem = Path(path).stem
            for candidate in (stem, f"{stem}_2", stem.removesuffix("_2")):
                candidate_path = f"lib/widgets/{candidate}.dart"
                if candidate_path in subtree_result.files:
                    best_path = candidate_path
                    best_assets = subtree_assets.get(candidate_path, frozenset())
                    best_score = 1.0
                    break

        if best_path is None or (best_score < 0.5 and not llm_syntax_broken):
            continue

        spec = spec_by_path.get(best_path)
        if (
            not llm_syntax_broken
            and spec is not None
            and len(llm_assets) >= spec.vector_count
        ):
            continue
        if (
            not llm_syntax_broken
            and spec is None
            and len(llm_assets) >= len(best_assets) * 0.6
        ):
            continue

        llm_class = _extract_widget_class_name(llm_content)
        subtree_class = _extract_widget_class_name(subtree_result.files[best_path])
        if llm_class is None or subtree_class is None:
            continue

        spec = spec_by_path.get(best_path)
        target_class = _resolve_merged_widget_class_name(
            llm_class=llm_class,
            subtree_class=subtree_class,
            spec_class=spec.class_name if spec is not None else None,
            used_class_names=_collect_widget_class_names(updated, exclude_paths=frozenset({path})),
        )
        merged = _rename_widget_class(subtree_result.files[best_path], subtree_class, target_class)
        updated[path] = merged

    for subtree_path, subtree_content in subtree_result.files.items():
        if subtree_path not in updated:
            continue
        current = updated[subtree_path]
        if current == subtree_content:
            continue
        llm_class = _extract_widget_class_name(current)
        subtree_class = _extract_widget_class_name(subtree_content)
        if llm_class is None or subtree_class is None:
            updated[subtree_path] = subtree_content
            continue
        spec = spec_by_path.get(subtree_path)
        target_class = _resolve_merged_widget_class_name(
            llm_class=llm_class,
            subtree_class=subtree_class,
            spec_class=spec.class_name if spec is not None else None,
            used_class_names=_collect_widget_class_names(
                updated,
                exclude_paths=frozenset({subtree_path}),
            ),
        )
        updated[subtree_path] = _rename_widget_class(subtree_content, subtree_class, target_class)

    return updated


def _primary_widget_class_region(screen_code: str) -> tuple[int, int]:
    """Return the byte range of the main screen widget class in ``screenCode``."""
    matches = list(_WIDGET_CLASS_DECL_RE.finditer(screen_code))
    if not matches:
        return 0, len(screen_code)
    chosen = matches[-1]
    for match in matches:
        name_match = re.search(
            r"class\s+(\w+)\s+extends\s+(?:StatelessWidget|StatefulWidget)",
            screen_code[match.start() : match.start() + 120],
        )
        if name_match is not None and name_match.group(1).endswith("Screen"):
            chosen = match
            break
    chosen_index = matches.index(chosen)
    region_start = chosen.start()
    region_end = (
        matches[chosen_index + 1].start()
        if chosen_index + 1 < len(matches)
        else len(screen_code)
    )
    return region_start, region_end


def _iter_positioned_blocks(
    screen_code: str,
    *,
    region_start: int = 0,
    region_end: int | None = None,
) -> Iterator[tuple[int, int, str]]:
    """Yield ``(start, paren_end, block)`` for standalone ``Positioned(`` calls."""
    end_bound = len(screen_code) if region_end is None else region_end
    index = region_start
    while index < end_bound:
        match = _POSITIONED_CALL_RE.search(screen_code, index, end_bound)
        if match is None:
            break
        start = match.start()
        paren_start = match.end() - 1
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None or paren_end >= end_bound:
            index = match.end()
            continue
        yield start, paren_end, screen_code[start : paren_end + 1]
        index = paren_end + 1


def _find_matching_paren(source: str, open_index: int) -> int | None:
    if open_index >= len(source) or source[open_index] != "(":
        return None
    depth = 0
    in_string = False
    string_quote = ""
    escape = False
    for index in range(open_index, len(source)):
        char = source[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == string_quote:
                in_string = False
            continue
        if char in {"'", '"'}:
            in_string = True
            string_quote = char
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _resolve_widget_class_name(
    planned_files: dict[str, str],
    subtree_result: SubtreeWidgetResult,
    spec: SubtreeWidgetSpec,
) -> str:
    widget_path = f"lib/widgets/{spec.file_name}.dart"
    widget_source = planned_files.get(widget_path, subtree_result.files.get(widget_path, ""))
    return _extract_widget_class_name(widget_source) or spec.class_name


def _value_near(value: str, expected: float, *, tolerance: float = 1.5) -> bool:
    try:
        return abs(float(value) - expected) <= tolerance
    except ValueError:
        return False


def _format_placement_token(value: float) -> str:
    return f"{value:g}" if value != int(value) else str(int(value))


def _block_uses_widget_child(block: str, class_name: str) -> bool:
    return bool(
        re.search(
            rf"child:\s*(?:const\s+)?{re.escape(class_name)}\s*\(\s*\)",
            block,
            re.DOTALL,
        )
    )


def _planned_widget_class_names(planned_files: dict[str, str]) -> frozenset[str]:
    names: set[str] = set()
    for path, content in planned_files.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        class_name = _extract_widget_class_name(content)
        if class_name:
            names.add(class_name)
    return frozenset(names)


def _block_uses_any_planned_widget_child(
    block: str,
    planned_files: dict[str, str],
) -> bool:
    for class_name in _planned_widget_class_names(planned_files):
        if _block_uses_widget_child(block, class_name):
            return True
    return False


def _block_matches_placement(
    block: str,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    tolerance: float = 4.0,
) -> bool:
    from figma_flutter_agent.generator.dart.postprocess import unscale_design_expressions

    normalized = unscale_design_expressions(block)
    left_match = re.search(r"left:\s*([\d.]+)", normalized)
    top_match = re.search(r"top:\s*([\d.]+)", normalized)
    width_match = re.search(r"width:\s*([\d.]+)", normalized)
    height_match = re.search(r"height:\s*([\d.]+)", normalized)
    if left_match is None or top_match is None:
        return False
    if not (
        _value_near(left_match.group(1), left, tolerance=tolerance)
        and _value_near(top_match.group(1), top, tolerance=tolerance)
    ):
        return False
    if width_match is not None and height_match is not None:
        return _value_near(width_match.group(1), width, tolerance=tolerance) and _value_near(
            height_match.group(1), height, tolerance=tolerance
        )
    right_match = re.search(r"right:\s*([\d.]+)", normalized)
    height_only_match = re.search(r"height:\s*([\d.]+)", normalized)
    return (
        right_match is not None
        and height_only_match is not None
        and _value_near(left_match.group(1), left, tolerance=tolerance)
        and _value_near(right_match.group(1), left, tolerance=tolerance)
        and _value_near(height_only_match.group(1), height, tolerance=tolerance)
    )


def _build_positioned_widget_replacement(
    *,
    class_name: str,
    left: float,
    top: float,
    width: float,
    height: float,
    figma_id: str | None = None,
) -> str:
    left_token = _format_placement_token(left)
    top_token = _format_placement_token(top)
    width_token = _format_placement_token(width)
    height_token = _format_placement_token(height)
    key_line = (
        f"                        key: ValueKey('figma-{figma_id}'),\n" if figma_id else ""
    )
    return (
        "Positioned(\n"
        f"                        left: {left_token},\n"
        f"                        top: {top_token},\n"
        f"                        width: {width_token},\n"
        f"                        height: {height_token},\n"
        f"{key_line}"
        f"                        child: const {class_name}(),\n"
        "                      )"
    )


def _should_insert_missing_subtree(spec: SubtreeWidgetSpec) -> bool:
    """Only insert screen-level subtrees; skip icon shards already inside a widget file."""
    placement = spec.representative.stack_placement
    if placement is None or placement.width is None or placement.height is None:
        return False
    area = float(placement.width) * float(placement.height)
    return area >= 5000.0 or placement.height >= 60.0 or placement.width >= 120.0


def insert_missing_subtree_widgets_at_placement(
    screen_code: str,
    *,
    subtree_result: SubtreeWidgetResult,
    planned_files: dict[str, str],
) -> str:
    """Insert ``const SubtreeWidget()`` layers omitted from LLM screen IR."""
    from figma_flutter_agent.generator.figma_anchor import (
        _design_stack_children_bounds,
        _finalize_spliced_dart_fragment,
        _inject_positioned_blocks_by_top,
        _sanitize_stack_children_segment,
    )

    bounds = _design_stack_children_bounds(screen_code)
    if bounds is None:
        return screen_code
    insert_start, insert_end = bounds
    segment = screen_code[insert_start:insert_end]
    to_insert: list[tuple[float, str]] = []
    for spec in subtree_result.specs:
        if not _should_insert_missing_subtree(spec):
            continue
        class_name = _resolve_widget_class_name(planned_files, subtree_result, spec)
        if re.search(rf"\b{re.escape(class_name)}\s*\(", screen_code):
            continue
        placement = spec.representative.stack_placement
        if placement is None or placement.width is None or placement.height is None:
            continue
        block = _build_positioned_widget_replacement(
            class_name=class_name,
            left=placement.left,
            top=placement.top,
            width=placement.width,
            height=placement.height,
            figma_id=spec.node_id,
        )
        to_insert.append((placement.top, block))
        logger.info(
            "Inserted missing subtree widget {} at top={} (figmaId={})",
            class_name,
            placement.top,
            spec.node_id,
        )
    if not to_insert:
        return screen_code
    updated_segment = _inject_positioned_blocks_by_top(
        _sanitize_stack_children_segment(segment),
        to_insert,
    )
    candidate = screen_code[:insert_start] + updated_segment.strip() + screen_code[insert_end:]
    return _finalize_spliced_dart_fragment(
        screen_code,
        candidate,
        label="subtree widget insert",
    )


def _replace_positioned_at_placement(
    screen_code: str,
    *,
    class_name: str,
    left: float,
    top: float,
    width: float,
    height: float,
    planned_files: dict[str, str] | None = None,
) -> str:
    """Replace the first Positioned block at Figma stackPlacement with a prebuilt widget."""
    region_start, region_end = _primary_widget_class_region(screen_code)
    for start, paren_end, block in _iter_positioned_blocks(
        screen_code,
        region_start=region_start,
        region_end=region_end,
    ):
        if _block_uses_widget_child(block, class_name):
            continue
        if planned_files is not None and _block_uses_any_planned_widget_child(
            block, planned_files
        ):
            continue
        if not _block_matches_placement(
            block,
            left=left,
            top=top,
            width=width,
            height=height,
        ):
            continue
        replacement = _build_positioned_widget_replacement(
            class_name=class_name,
            left=left,
            top=top,
            width=width,
            height=height,
        )
        candidate = screen_code[:start] + replacement + screen_code[paren_end + 1 :]
        return _accept_replacement_if_valid(screen_code, candidate, class_name=class_name)
    return screen_code


def _accept_replacement_if_valid(
    original: str,
    candidate: str,
    *,
    class_name: str,
) -> str:
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    delimiter_error = validate_dart_delimiters(candidate)
    if delimiter_error is None:
        return candidate
    logger.warning(
        "Skipped subtree Positioned replacement for {}: {}",
        class_name,
        delimiter_error,
    )
    return original


def _replace_empty_subtree_placeholder(
    screen_code: str,
    *,
    class_name: str,
    left: float,
    top: float,
    width: float,
    height: float,
) -> str:
    """Replace an empty ``SizedBox`` placeholder with a prebuilt subtree widget."""
    if re.search(rf"\b{re.escape(class_name)}\s*\(", screen_code):
        return screen_code

    region_start, region_end = _primary_widget_class_region(screen_code)
    for start, paren_end, block in _iter_positioned_blocks(
        screen_code,
        region_start=region_start,
        region_end=region_end,
    ):
        if not re.search(r"child:\s*(?:const\s+)?SizedBox\s*\(\s*\)", block):
            continue
        left_match = re.search(r"left:\s*([\d.]+)", block)
        top_match = re.search(r"top:\s*([\d.]+)", block)
        width_match = re.search(r"width:\s*([\d.]+)", block)
        height_match = re.search(r"height:\s*([\d.]+)", block)
        if (
            left_match is None
            or top_match is None
            or width_match is None
            or height_match is None
            or not _value_near(left_match.group(1), left)
            or not _value_near(top_match.group(1), top)
            or not _value_near(width_match.group(1), width)
            or not _value_near(height_match.group(1), height)
        ):
            continue
        child_re = r"child:\s*(?:const\s+)?SizedBox\s*\(\s*\)"
        new_block = re.sub(child_re, f"child: const {class_name}()", block, count=1)
        candidate = screen_code[:start] + new_block + screen_code[paren_end + 1 :]
        return _accept_replacement_if_valid(screen_code, candidate, class_name=class_name)
    return screen_code


def _collect_node_asset_keys(node: CleanDesignTreeNode) -> frozenset[str]:
    keys: set[str] = set()
    if node.vector_asset_key:
        keys.add(node.vector_asset_key)
    if node.image_asset_key:
        keys.add(node.image_asset_key)
    for child in node.children:
        keys.update(_collect_node_asset_keys(child))
    return frozenset(keys)


def _find_best_tree_node_for_assets(
    root: CleanDesignTreeNode,
    widget_assets: frozenset[str],
) -> CleanDesignTreeNode | None:
    """Return the clean-tree subtree that best matches a planned widget asset set."""
    if not widget_assets:
        return None
    ranked: list[tuple[float, CleanDesignTreeNode]] = []
    for node in _collect_all_nodes(root):
        node_assets = _collect_node_asset_keys(node)
        if not node_assets:
            continue
        overlap = len(node_assets & widget_assets)
        if overlap == 0:
            continue
        score = overlap / len(widget_assets)
        if score < 0.4:
            continue
        ranked.append((score, node))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    for _, node in ranked:
        if node.stack_placement is not None:
            return node
    return ranked[0][1]


def _collect_all_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_collect_all_nodes(child))
    return nodes


def _planned_widget_specs(
    planned_files: dict[str, str],
) -> list[tuple[str, frozenset[str], int]]:
    specs: list[tuple[str, frozenset[str], int]] = []
    for path, content in planned_files.items():
        if not path.startswith("lib/widgets/") or not path.endswith(".dart"):
            continue
        class_name = _extract_widget_class_name(content)
        assets = _extract_asset_paths(content)
        if class_name is None or not assets:
            continue
        specs.append((class_name, assets, len(assets)))
    specs.sort(key=lambda item: item[2], reverse=True)
    return specs


def _should_replace_block_with_widget(
    block: str,
    *,
    class_name: str,
    widget_assets: frozenset[str],
) -> bool:
    block_assets = _extract_asset_paths(block)
    overlap = block_assets & widget_assets
    if len(overlap) < max(1, math.ceil(len(widget_assets) * 0.4)):
        return False
    sole_widget = re.search(
        rf"child:\s*(?:const\s+)?{re.escape(class_name)}\s*\(\s*\)\s*(?:,|\))",
        block,
        re.DOTALL,
    )
    if sole_widget is not None and not block_assets:
        return False
    return bool(block_assets)


def _replace_positioned_inlining_with_widget(
    screen_code: str,
    *,
    class_name: str,
    widget_assets: frozenset[str],
    left: float,
    top: float,
    width: float,
    height: float,
) -> str:
    """Replace a Positioned block that inlines widget assets with ``const WidgetClass()``."""
    region_start, region_end = _primary_widget_class_region(screen_code)
    for start, paren_end, block in _iter_positioned_blocks(
        screen_code,
        region_start=region_start,
        region_end=region_end,
    ):
        if not _should_replace_block_with_widget(
            block,
            class_name=class_name,
            widget_assets=widget_assets,
        ):
            continue
        left_match = re.search(r"left:\s*([\d.]+)", block)
        if left_match is not None and not _value_near(left_match.group(1), left, tolerance=4.0):
            continue
        top_match = re.search(r"top:\s*([\d.]+)", block)
        if top_match is not None and not _value_near(top_match.group(1), top, tolerance=4.0):
            continue
        replacement = _build_positioned_widget_replacement(
            class_name=class_name,
            left=left,
            top=top,
            width=width,
            height=height,
        )
        candidate = screen_code[:start] + replacement + screen_code[paren_end + 1 :]
        return _accept_replacement_if_valid(screen_code, candidate, class_name=class_name)
    return screen_code


def force_subtree_widgets_at_placement(
    screen_code: str,
    *,
    subtree_result: SubtreeWidgetResult,
    planned_files: dict[str, str],
) -> str:
    """Pin prebuilt subtree widgets at their Figma stackPlacement regardless of LLM inlining."""
    updated = screen_code
    for spec in subtree_result.specs:
        placement = spec.representative.stack_placement
        if placement is None or placement.width is None or placement.height is None:
            continue
        class_name = _resolve_widget_class_name(planned_files, subtree_result, spec)
        updated = _replace_positioned_at_placement(
            updated,
            class_name=class_name,
            left=placement.left,
            top=placement.top,
            width=placement.width,
            height=placement.height,
            planned_files=planned_files,
        )
    return updated


def replace_inlined_planned_widgets(
    screen_code: str,
    *,
    planned_files: dict[str, str],
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Swap LLM-inlined SVG stacks for prebuilt widget classes when assets overlap."""
    updated = screen_code
    for class_name, widget_assets, _ in _planned_widget_specs(planned_files):
        node = _find_best_tree_node_for_assets(clean_tree, widget_assets)
        if node is None or node.stack_placement is None:
            continue
        placement = node.stack_placement
        if placement.width is None or placement.height is None:
            continue
        before = updated
        updated = _replace_positioned_at_placement(
            updated,
            class_name=class_name,
            left=placement.left,
            top=placement.top,
            width=placement.width,
            height=placement.height,
            planned_files=planned_files,
        )
        if updated != before:
            continue
        updated = _replace_positioned_inlining_with_widget(
            updated,
            class_name=class_name,
            widget_assets=widget_assets,
            left=placement.left,
            top=placement.top,
            width=placement.width,
            height=placement.height,
        )
    return updated


def _filter_outermost_social_stacks(
    candidates: list[CleanDesignTreeNode],
) -> list[CleanDesignTreeNode]:
    """Keep outermost social auth rows (drop inner groups that also match)."""
    if len(candidates) <= 1:
        return candidates

    def _descendant_of(ancestor: CleanDesignTreeNode, node: CleanDesignTreeNode) -> bool:
        if ancestor.id == node.id:
            return False
        return node.id in {item.id for item in _collect_all_nodes(ancestor)}

    outermost: list[CleanDesignTreeNode] = []
    for node in candidates:
        if any(_descendant_of(other, node) for other in candidates if other.id != node.id):
            continue
        outermost.append(node)
    return outermost


def _collect_social_auth_button_stacks(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    """Collect social sign-in rows using ``parser.geometry`` (no marketing copy)."""
    from figma_flutter_agent.parser.geometry import social_auth_row_confidence

    candidates: list[CleanDesignTreeNode] = []
    for node in _collect_all_nodes(root):
        if social_auth_row_confidence(node) >= _GEOMETRY_SOCIAL_ROW_CONFIDENCE:
            candidates.append(node)
    return _filter_outermost_social_stacks(candidates)


def _find_compact_icon_descendant(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    for child in node.children:
        if _is_compact_icon_subtree(child):
            return child
        nested = _find_compact_icon_descendant(child)
        if nested is not None:
            return nested
    return None


def _node_screen_bounds(
    root: CleanDesignTreeNode,
    node_id: str,
) -> tuple[float, float, float, float] | None:
    def walk(
        node: CleanDesignTreeNode,
        offset_left: float,
        offset_top: float,
    ) -> tuple[float, float, float, float] | None:
        placement = node.stack_placement
        left = offset_left + (placement.left if placement is not None else 0.0)
        top = offset_top + (placement.top if placement is not None else 0.0)
        if node.id == node_id:
            if placement is None or placement.width is None or placement.height is None:
                return None
            return left, top, placement.width, placement.height
        for child in node.children:
            found = walk(child, left, top)
            if found is not None:
                return found
        return None

    return walk(root, 0.0, 0.0)


def _resolve_planned_widget_class(
    node: CleanDesignTreeNode,
    planned_files: dict[str, str],
) -> str | None:
    node_assets = _collect_node_asset_keys(node)
    if not node_assets:
        return None
    for class_name, widget_assets, _ in _planned_widget_specs(planned_files):
        overlap = len(node_assets & widget_assets)
        if overlap >= max(1, math.ceil(len(widget_assets) * 0.4)):
            return class_name
    return None


def _figma_value_key(node_id: str) -> str:
    return f"figma-{node_id.replace(':', '_')}"


def _extract_button_label_layer(stack_block: str) -> str | None:
    center_match = re.search(r"\bCenter\s*\(", stack_block)
    if center_match is None:
        return None
    center_open = center_match.end() - 1
    center_close = _find_matching_paren(stack_block, center_open)
    if center_close is None:
        return None
    return stack_block[center_match.start() : center_close + 1]


def _build_auth_button_child_with_icon(
    *,
    icon_class: str,
    icon_left: float,
    label_layer: str,
) -> str:
    left_token = _format_placement_token(icon_left)
    return (
        "child: SizedBox.expand(\n"
        "                          child: Stack(\n"
        "                            fit: StackFit.expand,\n"
        "                            children: [\n"
        "                              Align(\n"
        "                                alignment: Alignment.centerLeft,\n"
        "                                child: Padding(\n"
        f"                                  padding: const EdgeInsets.only(left: {left_token}),\n"
        f"                                  child: const {icon_class}(),\n"
        "                                ),\n"
        "                              ),\n"
        f"                              {label_layer},\n"
        "                            ],\n"
        "                          ),\n"
        "                        )"
    )


def _replace_button_child_stack(
    button_block: str,
    *,
    new_child: str,
) -> str | None:
    stack_match = re.search(r"child:\s*Stack\s*\(", button_block, re.DOTALL)
    if stack_match is None:
        return None
    stack_open = stack_match.end() - 1
    stack_close = _find_matching_paren(button_block, stack_open)
    if stack_close is None:
        return None
    child_start = stack_match.start()
    return button_block[:child_start] + new_child + button_block[stack_close + 1 :]


def _remove_positioned_block(screen_code: str, start: int, paren_end: int) -> str:
    leading = screen_code[:start].rstrip()
    trailing = screen_code[paren_end + 1 :].lstrip()
    if trailing.startswith(","):
        trailing = trailing[1:].lstrip()
    elif leading.endswith(","):
        leading = leading[:-1].rstrip()
    return f"{leading}\n{trailing}" if leading and trailing else leading + trailing


def reconcile_auth_button_orphan_icons(
    screen_code: str,
    *,
    clean_tree: CleanDesignTreeNode,
    planned_files: dict[str, str],
) -> str:
    """Move screen-level icon widgets into their auth ``Button`` child stacks."""
    from figma_flutter_agent.parser.geometry import auth_button_confidence

    updated = screen_code
    for button in _collect_all_nodes(clean_tree):
        if auth_button_confidence(button) < _GEOMETRY_SOCIAL_ROW_CONFIDENCE:
            continue
        icon = _find_compact_icon_descendant(button)
        if icon is None:
            continue
        icon_bounds = _node_screen_bounds(clean_tree, icon.id)
        button_bounds = _node_screen_bounds(clean_tree, button.id)
        if icon_bounds is None or button_bounds is None:
            continue
        icon_left, icon_top, icon_width, icon_height = icon_bounds
        button_left, button_top, _button_width, _button_height = button_bounds
        icon_class = _resolve_planned_widget_class(icon, planned_files)
        if icon_class is None:
            continue

        def _find_orphan_positioned(
            source: str,
            _icon_class: str = icon_class,
            _icon_left: float = icon_left,
            _icon_top: float = icon_top,
            _icon_width: float = icon_width,
            _icon_height: float = icon_height,
        ) -> tuple[int, int] | None:
            region_start, region_end = _primary_widget_class_region(source)
            for start, paren_end, block in _iter_positioned_blocks(
                source,
                region_start=region_start,
                region_end=region_end,
            ):
                if not _block_uses_widget_child(block, _icon_class):
                    continue
                if re.search(r"\b(?:Outlined|Filled|Elevated|Text)Button\b", block):
                    continue
                if _block_matches_placement(
                    block,
                    left=_icon_left,
                    top=_icon_top,
                    width=_icon_width,
                    height=_icon_height,
                ):
                    return start, paren_end
            return None

        orphan_span = _find_orphan_positioned(updated)

        button_block_start: int | None = None
        button_block_end: int | None = None
        value_key = _figma_value_key(button.id)
        button_region_start, button_region_end = _primary_widget_class_region(updated)
        for start, paren_end, block in _iter_positioned_blocks(
            updated,
            region_start=button_region_start,
            region_end=button_region_end,
        ):
            if value_key not in block and not _block_matches_placement(
                block,
                left=button_left,
                top=button_top,
                width=button_bounds[2],
                height=button_bounds[3],
            ):
                continue
            if not re.search(r"\b(?:Outlined|Filled|Elevated|Text)Button\s*\(", block):
                continue
            button_block_start, button_block_end = start, paren_end
            break

        if button_block_start is None or button_block_end is None:
            continue
        button_block = updated[button_block_start : button_block_end + 1]
        if re.search(rf"\b{re.escape(icon_class)}\s*\(", button_block):
            if orphan_span is not None:
                orphan_start, orphan_end = orphan_span
                candidate = _remove_positioned_block(updated, orphan_start, orphan_end)
                updated = _accept_replacement_if_valid(
                    updated,
                    candidate,
                    class_name=icon_class,
                )
            continue

        stack_match = re.search(r"child:\s*Stack\s*\(", button_block, re.DOTALL)
        if stack_match is None:
            continue
        label_layer = _extract_button_label_layer(button_block[stack_match.start() :])
        if label_layer is None:
            continue
        rel_left = icon_left - button_left
        new_child = _build_auth_button_child_with_icon(
            icon_class=icon_class,
            icon_left=rel_left,
            label_layer=label_layer,
        )
        patched_button = _replace_button_child_stack(
            button_block,
            new_child=new_child,
        )
        if patched_button is None:
            continue
        candidate = (
            updated[:button_block_start] + patched_button + updated[button_block_end + 1 :]
        )
        updated = _accept_replacement_if_valid(
            updated,
            candidate,
            class_name=icon_class,
        )
        orphan_span = _find_orphan_positioned(updated)
        if orphan_span is not None:
            orphan_start, orphan_end = orphan_span
            candidate = _remove_positioned_block(updated, orphan_start, orphan_end)
            updated = _accept_replacement_if_valid(
                updated,
                candidate,
                class_name=icon_class,
            )
    return updated


def reconcile_llm_screen_with_subtrees(
    screen_code: str,
    *,
    subtree_result: SubtreeWidgetResult | None,
    planned_files: dict[str, str],
    clean_tree: CleanDesignTreeNode,
    uses_svg: bool = True,
) -> str:
    """Patch LLM screen bodies to use prebuilt subtree widgets and Figma-accurate copy."""
    from figma_flutter_agent.generator.dart.llm_codegen import apply_clean_tree_text_to_screen

    updated = screen_code
    if subtree_result is not None:
        updated = force_subtree_widgets_at_placement(
            updated,
            subtree_result=subtree_result,
            planned_files=planned_files,
        )
        updated = insert_missing_subtree_widgets_at_placement(
            updated,
            subtree_result=subtree_result,
            planned_files=planned_files,
        )
        for spec in subtree_result.specs:
            placement = spec.representative.stack_placement
            if placement is None or placement.width is None or placement.height is None:
                continue
            class_name = _resolve_widget_class_name(planned_files, subtree_result, spec)
            updated = _replace_empty_subtree_placeholder(
                updated,
                class_name=class_name,
                left=placement.left,
                top=placement.top,
                width=placement.width,
                height=placement.height,
            )
    updated = replace_inlined_planned_widgets(
        updated,
        planned_files=planned_files,
        clean_tree=clean_tree,
    )
    updated = apply_clean_tree_text_to_screen(updated, clean_tree)
    updated = reconcile_auth_button_orphan_icons(
        updated,
        clean_tree=clean_tree,
        planned_files=planned_files,
    )
    from figma_flutter_agent.generator.dart.postprocess import (
        strip_design_canvas_gesture_matryoshka,
    )

    updated = strip_design_canvas_gesture_matryoshka(updated)
    from figma_flutter_agent.generator.ambient_background import (
        ensure_centered_design_canvas,
        fix_ambient_background_responsiveness,
    )
    updated = fix_ambient_background_responsiveness(
        updated,
        clean_tree,
        uses_svg=uses_svg,
    )
    updated = ensure_centered_design_canvas(updated)
    from figma_flutter_agent.generator.planned.reconcile import (
        strip_inline_widget_duplicates_from_screen,
        strip_llm_relative_widget_imports,
    )

    updated = strip_llm_relative_widget_imports(updated)
    updated = strip_inline_widget_duplicates_from_screen(updated, planned_files)
    return _finalize_reconciled_screen(screen_code, updated)


def _finalize_reconciled_screen(original: str, reconciled: str) -> str:
    from figma_flutter_agent.generator.dart.llm_codegen import (
        repair_dart_delimiters,
        validate_dart_delimiters,
    )

    if validate_dart_delimiters(reconciled) is None:
        return reconciled
    repaired = repair_dart_delimiters(reconciled)
    if validate_dart_delimiters(repaired) is None:
        logger.warning(
            "Subtree reconcile produced invalid Dart syntax; keeping delimiter-repaired screenCode"
        )
        return repaired
    delimiter_error = validate_dart_delimiters(reconciled)
    logger.warning(
        "Subtree reconcile produced invalid Dart syntax ({}); keeping original screenCode",
        delimiter_error,
    )
    return original

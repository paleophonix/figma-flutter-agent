"""Visible-paint helpers for extracted widget materialization."""

from __future__ import annotations

import re

from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrNode

_ASSET_PATH_RE = re.compile(r"['\"](assets/[^'\"]+)['\"]")


def subtree_has_visible_paint(node: CleanDesignTreeNode, *, max_depth: int = 6) -> bool:
    """Return True when a subtree still carries drawable text, imagery, or controls."""
    if max_depth < 0:
        return False
    if node.type == NodeType.TEXT and (node.text or "").strip():
        return True
    if node.image_asset_key or node.vector_asset_key:
        return True
    if node.type in {NodeType.IMAGE, NodeType.VECTOR, NodeType.BUTTON}:
        return True
    return any(subtree_has_visible_paint(child, max_depth=max_depth - 1) for child in node.children)


def should_render_extracted_widget_from_clean_tree(
    widget_ir: WidgetIrNode,
    subtree: CleanDesignTreeNode,
) -> bool:
    """Prefer deterministic clean-tree emit when LLM IR omitted children but paint remains."""
    if widget_ir.children:
        return False
    if len(subtree.children) >= 2:
        return True
    return subtree_has_visible_paint(subtree)


def icon_badge_stack_intrinsic_glyph_size(
    subtree: CleanDesignTreeNode,
) -> tuple[float, float] | None:
    """Return drawable glyph bounds for compact icon badge stacks."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        _icon_badge_stack_has_glyph,
        layout_fact_icon_badge_stack,
    )

    if not layout_fact_icon_badge_stack(subtree):
        return None
    plate_w = float(subtree.sizing.width or 0)
    plate_h = float(subtree.sizing.height or 0)
    for child in subtree.children:
        if not _icon_badge_stack_has_glyph(child):
            continue
        glyph_w = float(child.sizing.width or 0)
        glyph_h = float(child.sizing.height or 0)
        if glyph_w <= 0 or glyph_h <= 0:
            continue
        if glyph_w < plate_w or glyph_h < plate_h:
            return glyph_w, glyph_h
    return None


def extracted_icon_badge_glyph_emit_needs_rematerialization(
    subtree: CleanDesignTreeNode,
    existing_code: str,
) -> bool:
    """Return True when cached extracted code stretched a badge glyph to the plate."""
    glyph = icon_badge_stack_intrinsic_glyph_size(subtree)
    if glyph is None:
        return False
    glyph_w, glyph_h = glyph
    glyph_w_token = format_geometry_literal(glyph_w)
    glyph_h_token = format_geometry_literal(glyph_h)
    if f"width: {glyph_w_token}" in existing_code and f"height: {glyph_h_token}" in existing_code:
        return False
    plate_w = subtree.sizing.width
    plate_h = subtree.sizing.height
    if plate_w is None or plate_h is None:
        return True
    plate_w_token = format_geometry_literal(float(plate_w))
    plate_h_token = format_geometry_literal(float(plate_h))
    plate_sized_glyph = (
        f"width: {plate_w_token}" in existing_code
        and f"height: {plate_h_token}" in existing_code
        and f"width: {glyph_w_token}" not in existing_code
    )
    if plate_sized_glyph and (
        "BoxFit.fill" in existing_code or "BoxFit.contain" in existing_code
    ):
        return True
    return plate_sized_glyph


def asset_path_family_key(path: str) -> str:
    """Normalize instance-specific SVG exports to a shared glyph/component family key."""
    name = path.rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0]
    if ";" in stem:
        return stem.split(";", 1)[1]
    return stem


def collect_subtree_asset_paths(node: CleanDesignTreeNode) -> frozenset[str]:
    """Collect bundled asset paths referenced by a clean-tree subtree."""
    paths: set[str] = set()
    if node.vector_asset_key:
        paths.add(node.vector_asset_key)
    if node.image_asset_key:
        paths.add(node.image_asset_key)
    for child in node.children:
        paths |= set(collect_subtree_asset_paths(child))
    return frozenset(paths)


def collect_subtree_asset_family_keys(node: CleanDesignTreeNode) -> frozenset[str]:
    """Collect normalized asset-family keys for a clean-tree subtree."""
    return frozenset(asset_path_family_key(path) for path in collect_subtree_asset_paths(node))


def extract_dart_asset_paths(code: str) -> frozenset[str]:
    """Extract bundled asset path literals from generated Dart source."""
    return frozenset(_ASSET_PATH_RE.findall(code))


def extract_dart_asset_family_keys(code: str) -> frozenset[str]:
    """Extract normalized asset-family keys from generated Dart source."""
    return frozenset(asset_path_family_key(path) for path in extract_dart_asset_paths(code))


def icon_badge_widget_identity_matches_subtree(
    existing_code: str,
    subtree: CleanDesignTreeNode,
) -> bool:
    """Return True when cached widget assets overlap the candidate badge subtree."""
    existing_assets = extract_dart_asset_family_keys(existing_code)
    if not existing_assets:
        return False
    subtree_assets = collect_subtree_asset_family_keys(subtree)
    if not subtree_assets:
        return False
    return bool(existing_assets & subtree_assets)


def icon_badge_planned_widget_needs_rematerialization(
    subtree: CleanDesignTreeNode,
    existing_code: str,
) -> bool:
    """Return True when a cached widget file stretched or dropped an icon-badge shell."""
    from figma_flutter_agent.generator.ir.extracted import (
        _extracted_widget_needs_decoration_rematerialization,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_icon_badge_stack,
    )

    if not layout_fact_icon_badge_stack(subtree):
        return False
    return extracted_icon_badge_glyph_emit_needs_rematerialization(
        subtree, existing_code
    ) or _extracted_widget_needs_decoration_rematerialization(subtree, existing_code)


def prefers_clean_tree_extracted_widget_emit(
    widget_ir: WidgetIrNode,
    subtree: CleanDesignTreeNode,
) -> bool:
    """Route icon badge stacks through deterministic layout emit instead of IR walk."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_icon_badge_stack,
    )

    if layout_fact_icon_badge_stack(subtree):
        return True
    return should_render_extracted_widget_from_clean_tree(widget_ir, subtree)

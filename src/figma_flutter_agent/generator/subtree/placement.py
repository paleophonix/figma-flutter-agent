"""Positioned block replacement and widget insertion."""

from __future__ import annotations

import re

from loguru import logger

from figma_flutter_agent.generator.subtree.blocks import (
    _accept_replacement_if_valid,
    _block_matches_placement,
    _block_uses_any_planned_widget_child,
    _block_uses_widget_child,
    _build_positioned_widget_replacement,
    _iter_positioned_blocks,
    _primary_widget_class_region,
    _resolve_widget_class_name,
    _value_near,
)
from figma_flutter_agent.generator.subtree.merge import (
    _extract_asset_paths,
    _find_best_tree_node_for_assets,
    _planned_widget_specs,
)
from figma_flutter_agent.generator.subtree.spec import SubtreeWidgetResult, SubtreeWidgetSpec
from figma_flutter_agent.schemas import CleanDesignTreeNode


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
    from figma_flutter_agent.generator.figma_anchor.blocks import (
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
        if planned_files is not None and _block_uses_any_planned_widget_child(block, planned_files):
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


def _should_replace_block_with_widget(
    block: str,
    *,
    class_name: str,
    widget_assets: frozenset[str],
) -> bool:
    import math

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

"""Inject deterministic layout Positioned blocks into LLM screen Dart."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.figma_anchor.blocks import (
    _design_stack_children_bounds,
    _extract_positioned_block,
    _finalize_spliced_dart_fragment,
    _find_node_by_id,
    _find_positioned_insert_index,
    _format_positioned_injection_batch,
    _merge_segment_prefix_and_batch,
    _positioned_block_needs_layout_upgrade,
    _positioned_top,
    _replace_positioned_block,
    _sanitize_stack_children_segment,
)
from figma_flutter_agent.generator.figma_anchor.collectors import (
    _collect_layout_injectable_node_ids,
    _collect_layout_upgrade_node_ids,
    _layout_inject_suppressed_for_content_widget,
)
from figma_flutter_agent.generator.figma_anchor.coverage import (
    _figma_key_present,
    _layout_node_covered_in_companion_sources,
    _layout_node_covered_in_sources,
)
from figma_flutter_agent.generator.figma_anchor.keys import (
    _normalize_layout_block_for_screen_embed,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode


def upgrade_incomplete_layout_positioned(
    screen_code: str,
    layout_code: str,
    root: CleanDesignTreeNode,
    *,
    companion_sources: tuple[str, ...] = (),
) -> str:
    """Replace simplified LLM chrome with full deterministic layout subtrees."""
    updated = screen_code
    for node_id in _collect_layout_upgrade_node_ids(root):
        node = _find_node_by_id(root, node_id)
        if _layout_node_covered_in_companion_sources(node_id, node, *companion_sources):
            continue
        if not _figma_key_present(updated, node_id):
            continue
        layout_block = _extract_positioned_block(layout_code, node_id)
        screen_block = _extract_positioned_block(updated, node_id)
        if layout_block is None or screen_block is None:
            continue
        if not _positioned_block_needs_layout_upgrade(screen_block, layout_block):
            continue
        layout_block = _normalize_layout_block_for_screen_embed(layout_block)
        candidate = _replace_positioned_block(updated, screen_block, layout_block)
        if candidate == updated:
            continue
        updated = candidate
        logger.info(
            "Upgraded incomplete layout Positioned for node {}",
            node_id,
        )
    return updated


def inject_missing_layout_positioned(
    screen_code: str,
    layout_code: str,
    root: CleanDesignTreeNode,
    *,
    companion_sources: tuple[str, ...] = (),
) -> str:
    """Splice deterministic ``Positioned`` widgets omitted from LLM ``screenCode``.

    When the LLM skips a ``BUTTON`` or link ``TEXT`` node that deterministic layout
    already rendered, copy the matching ``Positioned`` block from
    ``lib/generated/{feature}_layout.dart`` into the screen body.

    Args:
        screen_code: LLM screen ``build`` body source.
        layout_code: Deterministic layout file contents for the same feature.
        root: Clean design tree for node ids and vertical ordering.
        companion_sources: Additional Dart sources (extracted widgets, planned widget
            files) searched for existing Figma keys and visible copy before injecting.

    Returns:
        Updated screen Dart source.
    """
    if _layout_inject_suppressed_for_content_widget(screen_code, companion_sources):
        logger.info(
            "Skipping layout Positioned inject/upgrade: screen delegates body to content widget"
        )
        return screen_code
    decorative_only = bool(companion_sources)
    screen_code = upgrade_incomplete_layout_positioned(
        screen_code,
        layout_code,
        root,
        companion_sources=companion_sources,
    )
    bounds = _design_stack_children_bounds(screen_code)
    if bounds is None:
        return screen_code
    insert_start, insert_end = bounds
    existing_segment = screen_code[insert_start:insert_end]
    coverage_sources = (screen_code, *companion_sources)
    to_insert: list[tuple[float, str]] = []
    for node_id in _collect_layout_injectable_node_ids(
        root,
        decorative_only=decorative_only,
        layout_code=layout_code,
        screen_code=screen_code,
        companion_sources=companion_sources,
    ):
        node = _find_node_by_id(root, node_id)
        if _layout_node_covered_in_sources(node_id, node, *coverage_sources):
            continue
        block = _extract_positioned_block(layout_code, node_id)
        if block is None:
            continue
        block = _normalize_layout_block_for_screen_embed(block)
        top = node.stack_placement.top if node and node.stack_placement else _positioned_top(block)
        to_insert.append((top, block))
        kind = node.type.value if node is not None else "node"
        logger.info(
            "Injected missing layout Positioned for {} node {} (top={})",
            kind,
            node_id,
            top,
        )
    if not to_insert:
        return screen_code
    existing_segment = _sanitize_stack_children_segment(existing_segment)
    ordered = sorted(to_insert, key=lambda item: item[0])
    missing_blocks = [block for _, block in ordered if block.strip()]
    code_to_inject = _format_positioned_injection_batch(missing_blocks)
    insert_at = _find_positioned_insert_index(existing_segment, ordered[0][0])
    updated_segment = _merge_segment_prefix_and_batch(
        existing_segment[:insert_at],
        code_to_inject,
        existing_segment[insert_at:],
    )
    candidate = screen_code[:insert_start] + updated_segment.strip() + screen_code[insert_end:]
    return _finalize_spliced_dart_fragment(
        screen_code,
        candidate,
        label="layout Positioned inject",
    )

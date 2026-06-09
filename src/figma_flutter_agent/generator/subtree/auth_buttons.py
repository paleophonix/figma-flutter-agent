"""Social auth button reconciliation."""

from __future__ import annotations

import re

from figma_flutter_agent.schemas import CleanDesignTreeNode

from figma_flutter_agent.generator.subtree.spec import (
    _GEOMETRY_SOCIAL_ROW_CONFIDENCE,
    _is_compact_icon_subtree,
)
from figma_flutter_agent.generator.subtree.merge import (
    _collect_all_nodes,
    _collect_node_asset_keys,
    _planned_widget_specs,
)
from figma_flutter_agent.generator.subtree.placement import (
    _accept_replacement_if_valid,
    _block_matches_placement,
    _block_uses_widget_child,
    _find_matching_paren,
    _format_placement_token,
    _iter_positioned_blocks,
    _primary_widget_class_region,
)


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
    import math

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

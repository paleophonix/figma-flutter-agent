"""Positioned constraint fixing from the design tree."""

from __future__ import annotations

import re

from figma_flutter_agent.generator.dart.delimiters import (
    find_matching_paren as _find_matching_paren,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from .text_copy import sanitize_figma_display_text
from .text_richtext import _node_has_multiline_copy_in_dart_block


def _strip_positioned_height_from_block(block: str) -> str:
    return re.sub(
        r"(\n\s*)height:\s*[\d.]+,?\s*(?=\n\s*child:)",
        r"\1",
        block,
        count=1,
    )


def _positioned_has_edge(block: str, edge: str) -> bool:
    return re.search(rf"\b{edge}:\s*[\d.]+", block) is not None


def _drop_positioned_dimension(block: str, dimension: str) -> str:
    """Remove one ``width``/``height`` field from a ``Positioned`` argument list."""
    updated = re.sub(rf"\n\s*{dimension}:\s*[\d.]+,?\s*", "\n", block, count=1)
    if updated == block:
        updated = re.sub(rf",\s*{dimension}:\s*[\d.]+", "", block, count=1)
    return updated


def _normalize_positioned_block_constraints(block: str) -> str:
    """Drop ``width``/``height`` when opposing edges are also set (Flutter asserts)."""
    updated = block
    if (
        _positioned_has_edge(block, "left")
        and _positioned_has_edge(block, "right")
        and _positioned_has_edge(block, "width")
    ):
        updated = _drop_positioned_dimension(updated, "width")
    if (
        _positioned_has_edge(updated, "top")
        and _positioned_has_edge(updated, "bottom")
        and _positioned_has_edge(updated, "height")
    ):
        updated = _drop_positioned_dimension(updated, "height")
    return updated


def _format_layout_dimension(value: float) -> str:
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    return format_geometry_literal(value)


def _find_enclosing_positioned_span(screen_code: str, anchor: int) -> tuple[int, int] | None:
    pos_start = screen_code.rfind("Positioned(", 0, anchor)
    if pos_start == -1:
        return None
    paren_start = pos_start + len("Positioned")
    paren_end = _find_matching_paren(screen_code, paren_start)
    if paren_end is None:
        return None
    return pos_start, paren_end + 1


def _insert_positioned_size_fields(
    block: str,
    *,
    width: float | None = None,
    height: float | None = None,
) -> str:
    """Add missing ``width``/``height`` pins on a ``Positioned`` from Figma frame size."""
    insert_parts: list[str] = []
    if width is not None and not _positioned_has_edge(block, "width"):
        insert_parts.append(f"width: {_format_layout_dimension(width)},")
    if height is not None and not _positioned_has_edge(block, "height"):
        insert_parts.append(f"height: {_format_layout_dimension(height)},")
    if not insert_parts:
        return block
    insert = "\n                      ".join(insert_parts) + "\n                      "
    top_match = re.search(r"top:\s*[\d.]+,?\s*\n\s*", block)
    if top_match is not None:
        pos = top_match.end()
        return block[:pos] + insert + block[pos:]
    left_match = re.search(r"left:\s*[\d.]+,?\s*\n\s*", block)
    if left_match is not None:
        pos = left_match.end()
        return block[:pos] + insert + block[pos:]
    child_match = re.search(r"\n(\s*)child:", block)
    if child_match is not None:
        pos = child_match.start() + 1
        return block[:pos] + insert + block[pos:]
    return block


def fix_positioned_stack_bounds_from_tree(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Pin ``Positioned`` width/height from Figma for every keyed absolute child.

    LLM screen bodies often emit ``Positioned(left, top)`` without explicit frame
    size even when ``stackPlacement`` / ``sizing`` provide it, which breaks golden
    capture (unbounded ``Stack`` hosts).

    Args:
        screen_code: Sanitized LLM ``screenCode`` fragment.
        clean_tree: Parsed design tree with ``stackPlacement`` metadata.

    Returns:
        Dart source with bounded ``Positioned`` hosts where Figma provides sizes.
    """
    from figma_flutter_agent.generator.layout.widgets import figma_positioned_dimensions

    bounds_by_id: dict[str, tuple[float | None, float | None]] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        width, height = figma_positioned_dimensions(node)
        if width is not None or height is not None:
            bounds_by_id[node.id] = (width, height)
        for child in node.children:
            walk(child)

    walk(clean_tree)
    if not bounds_by_id:
        return screen_code

    replacements: dict[int, tuple[int, str]] = {}
    for node_id, (width, height) in bounds_by_id.items():
        if width is None and height is None:
            continue
        tokens = {node_id, node_id.replace(":", "_")}
        for token in tokens:
            pattern = f"figma-{token}"
            anchor = screen_code.find(pattern)
            if anchor == -1:
                continue
            span = _find_enclosing_positioned_span(screen_code, anchor)
            if span is None:
                continue
            start, end = span
            block = screen_code[start:end]
            patched = _insert_positioned_size_fields(block, width=width, height=height)
            if patched != block:
                replacements[start] = (end, patched)
            break

    updated = screen_code
    for start in sorted(replacements, reverse=True):
        end, patched = replacements[start]
        updated = updated[:start] + patched + updated[end:]
    return updated


def fix_invalid_positioned_constraints(screen_code: str) -> str:
    """Remove illegal ``Positioned`` dimension combinations across ``screenCode``."""
    replacements: list[tuple[int, int, str]] = []
    index = 0
    while True:
        start = screen_code.find("Positioned(", index)
        if start == -1:
            break
        paren_start = start + len("Positioned")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[start : paren_end + 1]
        index = paren_end + 1
        normalized = _normalize_positioned_block_constraints(block)
        if normalized != block:
            replacements.append((start, paren_end + 1, normalized))
    for start, end, patched_block in reversed(replacements):
        screen_code = screen_code[:start] + patched_block + screen_code[end:]
    return screen_code


def _patch_multiline_copy_column_width(screen_code: str, width: float) -> str:
    """Widen the Positioned Column that hosts multiline marketing copy."""
    from .text_copy import _copy_layout_width_for_metrics

    layout_width = _copy_layout_width_for_metrics(width)
    width_token = (
        f"{int(layout_width)}"
        if layout_width == int(layout_width)
        else f"{layout_width:g}"
    )
    replacements: list[tuple[int, int, str]] = []
    index = 0
    while True:
        start = screen_code.find("Positioned(", index)
        if start == -1:
            break
        paren_start = start + len("Positioned")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[start : paren_end + 1]
        index = paren_end + 1
        if "Column(" not in block:
            continue
        if not _node_has_multiline_copy_in_dart_block(block):
            continue
        if _positioned_has_edge(block, "right"):
            patched_block = _normalize_positioned_block_constraints(block)
            patched_block = _strip_positioned_height_from_block(patched_block)
            if patched_block != block:
                replacements.append((start, paren_end + 1, patched_block))
            continue
        if re.search(r"width:\s*[\d.]+", block):
            patched_block = re.sub(
                r"width:\s*[\d.]+", f"width: {width_token}", block, count=1
            )
        else:
            left_match = re.search(r"left:\s*([\d.]+)(?:\.0)?,\s*", block)
            if left_match is None:
                continue
            patched_block = re.sub(
                left_match.group(0),
                f"{left_match.group(0)}width: {width_token},\n                        ",
                block,
                count=1,
            )
        patched_block = _strip_positioned_height_from_block(patched_block)
        replacements.append((start, paren_end + 1, patched_block))
    for start, end, patched_block in reversed(replacements):
        screen_code = screen_code[:start] + patched_block + screen_code[end:]
    return screen_code


def _strip_multiline_copy_positioned_heights(screen_code: str) -> str:
    """Drop rigid Positioned heights on copy blocks (LLM often adds them back)."""
    replacements: list[tuple[int, int, str]] = []
    index = 0
    while True:
        start = screen_code.find("Positioned(", index)
        if start == -1:
            break
        paren_start = start + len("Positioned")
        paren_end = _find_matching_paren(screen_code, paren_start)
        if paren_end is None:
            break
        block = screen_code[start : paren_end + 1]
        index = paren_end + 1
        if "Column(" not in block or not _node_has_multiline_copy_in_dart_block(block):
            continue
        if not re.search(r"height:\s*[\d.]+", block):
            continue
        replacements.append(
            (start, paren_end + 1, _strip_positioned_height_from_block(block))
        )
    for start, end, patched_block in reversed(replacements):
        screen_code = screen_code[:start] + patched_block + screen_code[end:]
    return screen_code


def _node_has_multiline_copy(node: CleanDesignTreeNode) -> bool:
    if node.type == NodeType.TEXT and node.text:
        return "\n" in sanitize_figma_display_text(node.text)
    return any(_node_has_multiline_copy(child) for child in node.children)


def _first_text_descendant(node: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    if node.type == NodeType.TEXT and node.text:
        return node
    for child in node.children:
        found = _first_text_descendant(child)
        if found is not None:
            return found
    return None


def _collect_text_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes: list[CleanDesignTreeNode] = []
    if root.type == NodeType.TEXT and root.text:
        nodes.append(root)
    for child in root.children:
        nodes.extend(_collect_text_nodes(child))
    return nodes


def _collect_all_nodes(root: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    nodes = [root]
    for child in root.children:
        nodes.extend(_collect_all_nodes(child))
    return nodes


def _find_parent_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    for child in root.children:
        if child.id == node_id:
            return root
        found = _find_parent_node(child, node_id)
        if found is not None:
            return found
    return None


def _copy_layout_width_for_metrics(figma_width: float) -> float:
    """Add slack so Flutter font metrics do not clip Figma-sized copy blocks."""
    from .text_copy import _COPY_WIDTH_METRIC_SLACK

    slack_width = figma_width * _COPY_WIDTH_METRIC_SLACK
    return (
        round(slack_width, 1)
        if slack_width != int(slack_width)
        else float(int(slack_width))
    )


def _multiline_copy_column_width_from_tree(
    clean_tree: CleanDesignTreeNode,
) -> float | None:
    """Pick the Figma column width for copy blocks that contain intentional line breaks."""
    widths: list[float] = []
    for node in _collect_all_nodes(clean_tree):
        if node.type == NodeType.TEXT and node.text:
            sanitized = sanitize_figma_display_text(node.text)
            if "\n" in sanitized and node.sizing.width:
                widths.append(node.sizing.width)
        placement = node.stack_placement
        if placement is not None and placement.width and _node_has_multiline_copy(node):
            widths.append(placement.width)
    return max(widths) if widths else None


def expand_text_positioned_widths_from_tree(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Widen narrow Figma HUG text boxes so labels are not clipped in Flutter."""
    from figma_flutter_agent.parser.interaction import (
        button_stack_has_left_icon,
        stack_interaction_kind,
    )
    from .text_copy import _estimated_text_width, _figma_multiline_text_frame

    updated = screen_code
    for node in _collect_text_nodes(clean_tree):
        if node.text_spans or _figma_multiline_text_frame(node):
            continue
        parent = _find_parent_node(clean_tree, node.id)
        if parent is not None and stack_interaction_kind(parent) == "button":
            if button_stack_has_left_icon(parent):
                continue
        parent_width: float | None = None
        if parent is not None and parent.type == NodeType.STACK:
            parent_width = parent.sizing.width
            if parent.stack_placement is not None and parent.stack_placement.width is not None:
                parent_width = parent.stack_placement.width
        figma_text = (node.text or "").strip()
        target_width = _estimated_text_width(node)
        placement_width = (
            node.stack_placement.width if node.stack_placement is not None else None
        )
        if not figma_text or target_width is None or placement_width is None:
            continue
        min_width = max(placement_width, target_width)
        if (
            parent_width is not None
            and parent_width > 0
            and node.style.text_align == "CENTER"
        ):
            min_width = min(min_width, float(parent_width))
        if min_width <= placement_width + 1.5:
            continue
        escaped = re.escape(figma_text)
        for text_match in re.finditer(rf"Text\s*\(\s*['\"]({escaped})['\"]", updated):
            text_index = text_match.start()
            positioned_start = updated.rfind("Positioned(", 0, text_index)
            if positioned_start < 0:
                continue
            paren_open = updated.find("(", positioned_start)
            paren_close = _find_matching_paren(updated, paren_open)
            if paren_close is None or paren_close < text_index:
                continue
            block = updated[positioned_start : paren_close + 1]
            width_match = re.search(r"width:\s*([\d.]+)", block)
            if width_match is None:
                continue
            try:
                current_width = float(width_match.group(1))
            except ValueError:
                continue
            if current_width >= min_width - 1.0:
                continue
            width_token = (
                f"{min_width:g}" if min_width != int(min_width) else str(int(min_width))
            )
            new_block = re.sub(
                r"width:\s*[\d.]+",
                f"width: {width_token}",
                block,
                count=1,
            )
            updated = (
                updated[:positioned_start] + new_block + updated[paren_close + 1 :]
            )
            break
    return updated


def _strip_tight_text_positioned_heights(screen_code: str) -> str:
    """Drop fixed ``Positioned`` height on label rows that squash glyph metrics."""
    updated = screen_code
    search_from = 0
    while True:
        positioned_start = updated.find("Positioned(", search_from)
        if positioned_start < 0:
            break
        paren_open = updated.find("(", positioned_start)
        paren_close = _find_matching_paren(updated, paren_open)
        if paren_close is None:
            break
        block = updated[positioned_start : paren_close + 1]
        search_from = paren_close + 1
        if "Text(" not in block and "RichText(" not in block:
            continue
        height_match = re.search(r"height:\s*([\d.]+)", block)
        if height_match is None:
            continue
        font_match = re.search(r"fontSize:\s*([\d.]+)", block)
        if font_match is None:
            continue
        try:
            current_height = float(height_match.group(1))
            font_size = float(font_match.group(1))
        except ValueError:
            continue
        if current_height > font_size * 1.02:
            continue
        new_block = re.sub(r",?\s*height:\s*[\d.]+", "", block, count=1)
        if new_block == block:
            continue
        updated = updated[:positioned_start] + new_block + updated[paren_close + 1 :]
        search_from = positioned_start + len(new_block)
    return updated


def _relax_tight_text_positioned_heights(
    screen_code: str,
    clean_tree: CleanDesignTreeNode,
) -> str:
    """Widen tight Positioned heights around single-line labels (e.g. section dividers)."""
    from .text_copy import _target_text_positioned_height

    updated = screen_code
    for node in _collect_text_nodes(clean_tree):
        figma_text = (node.text or "").strip()
        min_height = _target_text_positioned_height(node)
        if not figma_text or min_height is None:
            continue
        escaped = re.escape(figma_text)
        for text_match in re.finditer(rf"Text\s*\(\s*['\"]({escaped})['\"]", updated):
            text_index = text_match.start()
            positioned_start = updated.rfind("Positioned(", 0, text_index)
            if positioned_start < 0:
                continue
            paren_open = updated.find("(", positioned_start)
            paren_close = _find_matching_paren(updated, paren_open)
            if paren_close is None or paren_close < text_index:
                continue
            block = updated[positioned_start : paren_close + 1]
            height_match = re.search(r"height:\s*([\d.]+)", block)
            if height_match is None:
                continue
            try:
                current_height = float(height_match.group(1))
            except ValueError:
                continue
            if current_height >= min_height - 0.5:
                continue
            height_token = (
                f"{min_height:g}"
                if min_height != int(min_height)
                else str(int(min_height))
            )
            new_block = re.sub(
                r"height:\s*[\d.]+",
                f"height: {height_token}",
                block,
                count=1,
            )
            updated = (
                updated[:positioned_start] + new_block + updated[paren_close + 1 :]
            )
            break
    return updated

"""Normalize Figma TEXT ``characters`` before clean-tree codegen."""

from __future__ import annotations

import re

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_MULTI_SPACE_BEFORE_NL = re.compile(r"[ \t]+\n")
_FIGMA_TRUNCATION_MARKERS = ("\u2026", "...")


def normalize_figma_characters(text: str) -> str:
    """Collapse stray spaces before line breaks and trim trailing whitespace."""
    if not text:
        return text
    normalized = _MULTI_SPACE_BEFORE_NL.sub("\n", text)
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).rstrip()


def has_figma_truncation_marker(text: str) -> bool:
    """Return True when Figma exported visible truncation at the end of ``text``."""
    return any(text.endswith(marker) for marker in _FIGMA_TRUNCATION_MARKERS)


def strip_figma_truncation_marker(text: str) -> str:
    """Remove a trailing Figma truncation glyph without inventing missing copy."""
    for marker in _FIGMA_TRUNCATION_MARKERS:
        if text.endswith(marker):
            return text[: -len(marker)]
    return text


def _collect_text_values(node: CleanDesignTreeNode) -> list[str]:
    """Return non-empty TEXT payloads under ``node``."""
    if node.type == NodeType.TEXT and node.text:
        return [node.text]
    values: list[str] = []
    for child in node.children:
        values.extend(_collect_text_values(child))
    return values


def _row_child_looks_like_chip_host(child: CleanDesignTreeNode) -> bool:
    """True when a bounded padded row/frame hosts badge/chip copy."""
    if child.type not in {NodeType.ROW, NodeType.CONTAINER}:
        return False
    width = child.sizing.width
    if width is None or width <= 0 or width > 140.0:
        return False
    padding = child.padding
    if padding is None:
        return False
    horizontal_pad = float(padding.left or 0.0) + float(padding.right or 0.0)
    return horizontal_pad >= 8.0


def recover_truncated_row_heading_text(
    text: str,
    *,
    row: CleanDesignTreeNode,
) -> str:
    """Recover heading copy truncated in Figma REST beside a longer chip label."""
    if not has_figma_truncation_marker(text):
        return text
    stem = strip_figma_truncation_marker(text)
    best = stem
    for sibling in row.children:
        if not _row_child_looks_like_chip_host(sibling):
            continue
        for chip_text in _collect_text_values(sibling):
            if chip_text.startswith(stem) and len(chip_text) > len(best):
                best = chip_text
    return best


def _replace_text_node(
    node: CleanDesignTreeNode,
    *,
    node_id: str,
    text: str,
) -> CleanDesignTreeNode:
    if node.id == node_id and node.type == NodeType.TEXT:
        return node.model_copy(update={"text": text, "accessibility_label": text})
    if not node.children:
        return node
    return node.model_copy(
        update={
            "children": [
                _replace_text_node(child, node_id=node_id, text=text) for child in node.children
            ]
        }
    )


def reconcile_truncated_row_heading_text_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Restore row-heading copy when Figma REST ends with a truncation marker."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.ROW:
            return node

        updated_children: list[CleanDesignTreeNode] = []
        for child in node.children:
            if child.type != NodeType.COLUMN:
                updated_children.append(child)
                continue
            text_nodes = [item for item in child.children if item.type == NodeType.TEXT]
            if len(text_nodes) != 1 or not text_nodes[0].text:
                updated_children.append(child)
                continue
            text_node = text_nodes[0]
            if not has_figma_truncation_marker(text_node.text):
                updated_children.append(child)
                continue
            recovered = recover_truncated_row_heading_text(text_node.text, row=node)
            next_child = child
            if recovered != text_node.text:
                next_child = _replace_text_node(child, node_id=text_node.id, text=recovered)
            if next_child.sizing.width_mode == SizingMode.HUG:
                next_child = next_child.model_copy(
                    update={
                        "sizing": next_child.sizing.model_copy(
                            update={"width_mode": SizingMode.FILL},
                        ),
                    },
                )
            updated_children.append(next_child)
        return node.model_copy(update={"children": updated_children})

    return walk(root)

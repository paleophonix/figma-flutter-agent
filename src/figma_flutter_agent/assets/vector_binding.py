"""Validate visible vector nodes have drawable asset bindings after export."""

from __future__ import annotations

from figma_flutter_agent.errors import MissingVectorAssetError
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_TRANSPARENT_FILLS = frozenset({"0x00000000", "transparent", None})


def _vector_has_visible_paint(node: CleanDesignTreeNode) -> bool:
    """Return True when a VECTOR node should render visible paint without an asset."""
    if node.type != NodeType.VECTOR:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is not None and width <= 0:
        return False
    if height is not None and height <= 0:
        return False
    if node.vector_asset_key or node.image_asset_key:
        return False
    style = node.style
    if style.has_stroke:
        return True
    return style.background_color not in _TRANSPARENT_FILLS


def collect_unbound_visible_vector_ids(root: CleanDesignTreeNode) -> list[str]:
    """List visible VECTOR node ids that lack drawable asset keys.

    Args:
        root: Parsed clean design tree root.

    Returns:
        Sorted node ids missing ``vector_asset_key`` and ``image_asset_key``.
    """
    found: list[str] = []

    def walk(node: CleanDesignTreeNode) -> None:
        if _vector_has_visible_paint(node):
            found.append(node.id)
        for child in node.children:
            walk(child)

    walk(root)
    return sorted(found)


def assert_visible_vectors_bound(
    root: CleanDesignTreeNode,
    *,
    strict: bool,
    failed_export_node_ids: frozenset[str] | None = None,
    destination_trees: dict[str, CleanDesignTreeNode] | None = None,
) -> list[str]:
    """Raise when strict mode requires drawable assets for visible vectors.

    Args:
        root: Primary screen clean tree.
        strict: When True, unbound visible vectors abort the pipeline.
        failed_export_node_ids: Optional Figma Images API failures for context.
        destination_trees: Optional prototype destination trees to scan.

    Returns:
        Unbound visible vector node ids when ``strict`` is False.

    Raises:
        MissingVectorAssetError: When ``strict`` is True and vectors remain unbound.
    """
    unbound = collect_unbound_visible_vector_ids(root)
    if destination_trees:
        for tree in destination_trees.values():
            for node_id in collect_unbound_visible_vector_ids(tree):
                if node_id not in unbound:
                    unbound.append(node_id)
        unbound.sort()
    if not unbound or not strict:
        return unbound
    preview = ", ".join(unbound[:8])
    if len(unbound) > 8:
        preview = f"{preview} (+{len(unbound) - 8} more)"
    export_hint = ""
    if failed_export_node_ids:
        overlap = sorted(node_id for node_id in unbound if node_id in failed_export_node_ids)
        if overlap:
            export_preview = ", ".join(overlap[:8])
            if len(overlap) > 8:
                export_preview = f"{export_preview} (+{len(overlap) - 8} more)"
            export_hint = f" Figma Images API export failed for: {export_preview}."
    raise MissingVectorAssetError(
        f"Visible vector node(s) lack exported drawable assets: {preview}.{export_hint}"
    )

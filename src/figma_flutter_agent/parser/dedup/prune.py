"""Clean-tree pruning after widget deduplication."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_DECORATIVE_VECTOR_MAX_WIDTH_PX = 300.0
_BACKGROUND_CONTAINER_MIN_SCREEN_FRACTION = 0.5
_MAX_COMPACT_LABELED_INPUT_HEIGHT = 120.0


def _cluster_duplicate_keeps_subtree(node: CleanDesignTreeNode) -> bool:
    """Keep duplicate cluster subtrees for compact labeled flex ``INPUT`` fields."""
    from figma_flutter_agent.parser.dedup.form_field_cluster import (
        _is_compact_form_field_cluster_input,
        is_compact_flex_form_field_host,
    )

    if is_compact_flex_form_field_host(node):
        return True
    return _is_compact_form_field_cluster_input(node)


def prune_top_level_cluster_duplicates(root: CleanDesignTreeNode) -> None:
    """No-op: ``prune_duplicated_cluster_subtrees`` dedups clusters at every depth."""


def prune_extracted_subtree_nodes(
    root: CleanDesignTreeNode,
    extracted_node_ids: frozenset[str],
) -> None:
    """Drop nodes already rendered as subtree widgets from the layout tree."""
    if not extracted_node_ids:
        return

    def walk(node: CleanDesignTreeNode) -> None:
        node.children = [child for child in node.children if child.id not in extracted_node_ids]
        for child in node.children:
            walk(child)

    walk(root)


def is_decorative_absolute_vector(
    node: CleanDesignTreeNode,
    *,
    root: CleanDesignTreeNode | None = None,
) -> bool:
    """True for ambient Figma ``Vector`` blobs that should not become layout widgets."""
    if root is not None and _protected_by_large_background_container(node, root):
        return False
    if node.layout_positioning != "ABSOLUTE":
        return False
    if "Vector" not in node.name:
        return False
    width = _node_layout_width_px(node)
    if width is None or width >= _DECORATIVE_VECTOR_MAX_WIDTH_PX:
        return False
    return node.type == NodeType.VECTOR


def prune_decorative_absolute_vectors(root: CleanDesignTreeNode) -> int:
    """Drop top-level absolute ``Vector`` dust."""
    removed = 0
    kept: list[CleanDesignTreeNode] = []
    for child in root.children:
        if is_decorative_absolute_vector(child, root=root):
            removed += 1
            continue
        kept.append(child)
    root.children = kept
    return removed


def prune_generation_layout_tree(
    root: CleanDesignTreeNode,
    *,
    extracted_subtree_node_ids: frozenset[str] = frozenset(),
    checkpoint: str | None = "CP0b_reprune",
) -> None:
    """True subtree pruning for the codegen pool (LLM, layout, anchors).

    Args:
        root: Clean design tree to prune in place.
        extracted_subtree_node_ids: Subtree widget roots to drop from layout pool.
        checkpoint: Conservation checkpoint id (``CP0_parse``, ``CP0b_reprune``, or
            ``None`` to skip validation — tests only).
    """

    def _prune() -> None:
        prune_extracted_subtree_nodes(root, extracted_subtree_node_ids)
        prune_top_level_cluster_duplicates(root)
        prune_duplicated_cluster_subtrees(root)

    if checkpoint is None:
        _prune()
        return

    from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
        run_cp0_parse_dedup,
        run_cp0b_reprune,
    )
    from figma_flutter_agent.generator.geometry.invariants.conservation import (
        collect_subtree_node_ids,
    )

    allowed_removed = (
        collect_subtree_node_ids(root, extracted_subtree_node_ids)
        if extracted_subtree_node_ids
        else None
    )
    if checkpoint == "CP0_parse":
        run_cp0_parse_dedup(root, prune_fn=_prune)
        return
    run_cp0b_reprune(
        root,
        prune_fn=_prune,
        allowed_removed_ids=allowed_removed,
    )


def prune_duplicated_cluster_subtrees(root: CleanDesignTreeNode) -> None:
    """Clear ``children`` on repeated ``cluster_id`` instances and link ref stubs."""
    seen_clusters: set[str] = set()
    cluster_assets: dict[str, tuple[str | None, str | None]] = {}

    def walk(node: CleanDesignTreeNode, parent: CleanDesignTreeNode | None) -> None:
        cluster_id = node.cluster_id
        parent_width = parent.sizing.width if parent is not None else None
        if cluster_id and cluster_id in seen_clusters:
            if parent is not None and parent.type in {NodeType.TABS, NodeType.CAROUSEL}:
                for child in node.children:
                    walk(child, node)
                return
            from figma_flutter_agent.generator.layout.flex_policy import (
                row_is_status_pill_badge,
                row_is_tight_horizontal_pill_label,
            )
            from figma_flutter_agent.parser.interaction import hosts_compact_checkbox_control

            if (
                row_is_tight_horizontal_pill_label(node)
                or row_is_status_pill_badge(node)
                or hosts_compact_checkbox_control(node)
            ):
                for child in node.children:
                    walk(child, node)
                return
            if _cluster_duplicate_keeps_subtree(node):
                for child in node.children:
                    walk(child, node)
                return
            from figma_flutter_agent.generator.cluster_variants import primary_vector_asset
            from figma_flutter_agent.parser.boundaries.ids import collect_descendant_figma_ids

            flattened = collect_descendant_figma_ids(node)
            if flattened:
                node.flatten_figma_node_ids = flattened
            asset = primary_vector_asset(node) or node.vector_asset_key
            if asset is None:
                forward, backward = cluster_assets.get(cluster_id, (None, None))
                asset = (
                    backward
                    if _cluster_instance_is_backward(node, parent_width=parent_width)
                    else forward
                )
            if asset is not None:
                node.vector_asset_key = asset
            from figma_flutter_agent.parser.interaction import (
                extract_cart_quantity_digit,
                looks_like_cart_quantity_scrim_row,
            )

            if looks_like_cart_quantity_scrim_row(node):
                digit = extract_cart_quantity_digit(node)
                if digit is not None:
                    node.text = digit
            node.children = []
            return
        if cluster_id:
            from figma_flutter_agent.generator.cluster_variants import primary_vector_asset

            asset = primary_vector_asset(node)
            if asset is not None:
                forward, backward = cluster_assets.get(cluster_id, (None, None))
                if _cluster_instance_is_backward(node, parent_width=parent_width):
                    backward = asset
                else:
                    forward = asset
                cluster_assets[cluster_id] = (forward, backward)
            seen_clusters.add(cluster_id)
        for child in node.children:
            walk(child, node)

    walk(root, None)


def _node_layout_width_px(node: CleanDesignTreeNode) -> float | None:
    width = node.sizing.width
    if width is not None:
        return float(width)
    if node.stack_placement is not None and node.stack_placement.width is not None:
        return float(node.stack_placement.width)
    return None


def _screen_canvas_size(root: CleanDesignTreeNode) -> tuple[float, float]:
    width = root.sizing.width
    height = root.sizing.height
    if width is None or height is None:
        for child in root.children:
            placement = child.stack_placement
            if placement is None:
                continue
            if width is None and placement.width is not None:
                width = placement.width
            if height is None and placement.height is not None:
                height = placement.height
    return float(width or 414.0), float(height or 896.0)


def _is_large_background_container(
    node: CleanDesignTreeNode,
    *,
    canvas_width: float,
    canvas_height: float,
) -> bool:
    name_lower = node.name.lower()
    if "background" not in name_lower and "group" not in name_lower:
        return False
    width = _node_layout_width_px(node)
    height = node.sizing.height
    if height is None and node.stack_placement is not None:
        height = node.stack_placement.height
    if width is None or height is None:
        return False
    return (
        width >= canvas_width * _BACKGROUND_CONTAINER_MIN_SCREEN_FRACTION
        and height >= canvas_height * _BACKGROUND_CONTAINER_MIN_SCREEN_FRACTION
    )


def _node_within_container(node: CleanDesignTreeNode, container: CleanDesignTreeNode) -> bool:
    placement = node.stack_placement
    bounds = container.stack_placement
    if placement is None or bounds is None:
        return False
    if placement.left is None or placement.top is None:
        return False
    left = bounds.left or 0.0
    top = bounds.top or 0.0
    width = bounds.width
    height = bounds.height
    if width is None or height is None:
        return False
    node_width = placement.width or 0.0
    node_height = placement.height or 0.0
    center_x = placement.left + node_width / 2.0
    center_y = placement.top + node_height / 2.0
    return left <= center_x <= left + width and top <= center_y <= top + height


def _protected_by_large_background_container(
    node: CleanDesignTreeNode,
    root: CleanDesignTreeNode,
) -> bool:
    canvas_width, canvas_height = _screen_canvas_size(root)
    for child in root.children:
        if child.type not in {NodeType.STACK, NodeType.CONTAINER, NodeType.COLUMN, NodeType.ROW}:
            continue
        if not _is_large_background_container(
            child,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
        ):
            continue
        if _node_within_container(node, child):
            return True
    return False


def _cluster_instance_is_backward(
    node: CleanDesignTreeNode,
    *,
    parent_width: float | None,
) -> bool:
    """Infer rewind vs forward skip from horizontal placement within the parent row."""
    from figma_flutter_agent.parser.interaction import skip_control_left_side_of_parent

    return skip_control_left_side_of_parent(node, parent_width=parent_width)

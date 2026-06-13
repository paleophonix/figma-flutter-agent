"""Grid-level layout reconcilers for clean design tree nodes."""

from __future__ import annotations

from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
)

from .reconcilers_grid_hydrate import (
    _build_product_card_template_lookup,
    _build_pruned_cluster_alias_lookup,
    _grid_product_tile_fidelity_score,
    _hydrate_grid_cards_from_templates,
    _product_card_has_inline_tile_content,
)

_PRODUCT_GRID_MIN_CARDS = 2


def _grid_child_visual_left(node: CleanDesignTreeNode) -> float:
    """Return the paint-space left edge for ordering GRID children left-to-right."""
    frame = node.geometry_frame
    if frame is not None:
        if frame.world_aabb is not None and frame.world_aabb.x is not None:
            return float(frame.world_aabb.x)
        if frame.parsed_world_aabb is not None and frame.parsed_world_aabb.x is not None:
            return float(frame.parsed_world_aabb.x)
    if node.children:
        return _grid_child_visual_left(node.children[0])
    return 0.0


def reconcile_grid_child_visual_order_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Sort GRID children by world left edge so emit matches Figma paint order."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.GRID or len(node.children) < 2:
            return node
        ordered = sorted(
            node.children,
            key=lambda child: (_grid_child_visual_left(child), child.id),
        )
        if [child.id for child in ordered] == [child.id for child in node.children]:
            return node
        return node.model_copy(update={"children": ordered})

    return walk(root)


def _grid_is_product_recommendation_grid(node: CleanDesignTreeNode) -> bool:
    """Two-up product tile grids (CARD children with edge-to-edge hero imagery)."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        card_has_edge_to_edge_hero_stack,
    )

    if node.type != NodeType.GRID or len(node.children) < _PRODUCT_GRID_MIN_CARDS:
        return False
    columns = node.grid_column_count
    if columns is not None and columns < 2:
        return False
    cards = [child for child in node.children if child.type == NodeType.CARD]
    if len(cards) < _PRODUCT_GRID_MIN_CARDS:
        return False
    hero_cards = sum(1 for card in cards if card_has_edge_to_edge_hero_stack(card))
    return hero_cards >= _PRODUCT_GRID_MIN_CARDS


def _product_grids_are_structural_duplicates(
    left: CleanDesignTreeNode,
    right: CleanDesignTreeNode,
) -> bool:
    """True when two grids are the same Figma duplicate product-card row."""
    if not _grid_is_product_recommendation_grid(left):
        return False
    if not _grid_is_product_recommendation_grid(right):
        return False
    if left.grid_column_count != right.grid_column_count:
        return False
    if len(left.children) != len(right.children):
        return False
    if left.grid_row_gap != right.grid_row_gap:
        return False
    return left.grid_column_gap == right.grid_column_gap


def reconcile_duplicate_product_card_grids_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Keep stacked duplicate product-card GRID rows and hydrate pruned card copies."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.COLUMN:
            return node

        patched_children: list[CleanDesignTreeNode] = []
        index = 0
        while index < len(node.children):
            child = node.children[index]
            if not _grid_is_product_recommendation_grid(child):
                patched_children.append(child)
                index += 1
                continue

            duplicate_run = [child]
            cursor = index + 1
            while cursor < len(node.children):
                candidate = node.children[cursor]
                if _product_grids_are_structural_duplicates(duplicate_run[0], candidate):
                    duplicate_run.append(candidate)
                    cursor += 1
                else:
                    break

            if len(duplicate_run) == 1:
                patched_children.append(child)
            else:
                best = max(duplicate_run, key=_grid_product_tile_fidelity_score)
                template_cards = [
                    item for item in best.children if item.type == NodeType.CARD
                ]
                pruned_cards = [
                    card
                    for grid in duplicate_run
                    for card in grid.children
                    if card.type == NodeType.CARD
                    and not _product_card_has_inline_tile_content(card)
                ]
                template_by_key = _build_product_card_template_lookup(template_cards)
                template_by_key.update(
                    _build_pruned_cluster_alias_lookup(template_cards, pruned_cards)
                )
                for grid in duplicate_run:
                    hydrated_children = _hydrate_grid_cards_from_templates(
                        grid,
                        template_cards,
                        template_by_key=template_by_key,
                    )
                    patched_children.append(
                        grid.model_copy(update={"children": hydrated_children})
                    )
            index = cursor

        return node.model_copy(update={"children": patched_children})

    return walk(root)

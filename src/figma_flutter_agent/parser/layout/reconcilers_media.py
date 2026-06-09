"""Media and layout-host reconcilers: promo cards, playback timestamps, flex promotion."""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
)

_PROMO_CARD_MIN_WIDTH_PX = 120.0
_PROMO_CARD_MAX_WIDTH_PX = 400.0
_PROMO_CARD_MIN_HEIGHT_PX = 80.0
_PROMO_CARD_MAX_HEIGHT_PX = 260.0
_PROMO_CARD_ROW_TOP_SPREAD_PX = 56.0
_HERO_PHOTO_VIEWPORT_DRIFT_PX = 0.25

_FLEX_LAYOUT_HOST_TYPES = frozenset(
    {
        NodeType.ROW,
        NodeType.COLUMN,
        NodeType.CONTAINER,
        NodeType.WRAP,
        NodeType.GRID,
    }
)


def _is_promo_card_stack(node: CleanDesignTreeNode) -> bool:
    """Side-by-side course/music promo tiles on feed screens."""
    if node.type != NodeType.STACK or node.stack_placement is None:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    return (
        _PROMO_CARD_MIN_WIDTH_PX <= width <= _PROMO_CARD_MAX_WIDTH_PX
        and _PROMO_CARD_MIN_HEIGHT_PX <= height <= _PROMO_CARD_MAX_HEIGHT_PX
    )


def _stack_has_playback_timestamps(node: CleanDesignTreeNode) -> bool:
    """True when a stack row contains clock labels and a wide progress track."""
    if node.type != NodeType.STACK:
        return False
    stamps = [
        child
        for child in node.children
        if child.type == NodeType.TEXT and child.text and ":" in child.text
    ]
    if len(stamps) < 2:
        return False
    wide = [
        child
        for child in node.children
        if child.type in {NodeType.VECTOR, NodeType.SLIDER}
        and float(child.sizing.width or 0.0) >= 200.0
    ]
    return bool(wide)


def reconcile_promo_card_row_tops_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Align promo cards that share a row to the same ``top`` baseline."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.STACK:
            return node
        promos = [child for child in node.children if _is_promo_card_stack(child)]
        if len(promos) < 2:
            return node
        tops: list[float] = []
        for child in promos:
            placement = child.stack_placement
            if placement is None or placement.top is None:
                continue
            tops.append(float(placement.top))
        if len(tops) < 2:
            return node
        if max(tops) - min(tops) > _PROMO_CARD_ROW_TOP_SPREAD_PX:
            return node
        aligned_top = round_geometry(min(tops))
        if aligned_top is None:
            return node
        promo_ids = {child.id for child in promos}
        patched_children: list[CleanDesignTreeNode] = []
        for child in node.children:
            if child.id not in promo_ids:
                patched_children.append(child)
                continue
            placement = child.stack_placement
            if placement is None:
                patched_children.append(child)
                continue
            patched_children.append(
                child.model_copy(
                    update={
                        "stack_placement": placement.model_copy(
                            update={"top": aligned_top},
                        ),
                    },
                ),
            )
        return node.model_copy(update={"children": patched_children})

    return walk(root)


def promote_flex_hosts_with_absolute_children(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Promote auto-layout hosts to STACK when they contain absolutely positioned children.

    Args:
        root: Parsed clean design tree.

    Returns:
        Tree with flex hosts rewritten to ``NodeType.STACK`` where needed.
    """
    children = [
        promote_flex_hosts_with_absolute_children(child) for child in root.children
    ]
    node = root.model_copy(update={"children": children})
    if node.type in _FLEX_LAYOUT_HOST_TYPES and any(
        child.stack_placement is not None for child in node.children
    ):
        return node.model_copy(update={"type": NodeType.STACK})
    return node


def reconcile_playback_timestamp_row_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Align MM:SS labels on the same baseline inside a media timeline stack."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if not _stack_has_playback_timestamps(node):
            return node
        stamp_nodes = [
            child
            for child in node.children
            if child.type == NodeType.TEXT and child.text and ":" in child.text
        ]
        tops: list[float] = []
        for child in stamp_nodes:
            placement = child.stack_placement
            if placement is None:
                continue
            top = placement.top
            if top is None and placement.bottom is not None:
                parent_height = float(node.sizing.height or 0.0)
                height = float(placement.height or child.sizing.height or 0.0)
                if parent_height > 0 and height > 0:
                    top = parent_height - float(placement.bottom) - height
            if top is not None:
                tops.append(float(top))
        if not tops:
            return node
        aligned_top = max(tops)
        stamp_ids = {item.id for item in stamp_nodes}
        patched_children: list[CleanDesignTreeNode] = []
        for child in node.children:
            if child.id not in stamp_ids:
                patched_children.append(child)
                continue
            placement = child.stack_placement
            if placement is None:
                patched_children.append(child)
                continue
            current_top = placement.top
            if current_top is not None and abs(float(current_top) - aligned_top) <= 0.5:
                patched_children.append(child)
                continue
            patched_children.append(
                child.model_copy(
                    update={
                        "stack_placement": placement.model_copy(
                            update={"top": round_geometry(aligned_top)},
                        ),
                    },
                ),
            )
        return node.model_copy(update={"children": patched_children})

    return walk(root)


def _photo_is_hero_full_bleed(photo: CleanDesignTreeNode) -> bool:
    """Return True when a raster leaf is pinned to fill a product hero viewport."""
    if not photo.image_asset_key or photo.children:
        return False
    placement = photo.stack_placement
    if placement is None:
        return True
    horizontal = (placement.horizontal or "LEFT").upper()
    vertical = (placement.vertical or "TOP").upper()
    return horizontal in {"LEFT_RIGHT", "LEFT", "RIGHT", "STRETCH"} and vertical in {
        "TOP_BOTTOM",
        "TOP",
        "BOTTOM",
        "STRETCH",
    }


def _reconcile_hero_photo_viewport(hero: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Snap a full-bleed hero raster leaf to the hero stack viewport dimensions."""
    from figma_flutter_agent.schemas.geometry import GeomRect

    if hero.type != NodeType.STACK or not hero.children:
        return hero
    photo = hero.children[0]
    if photo.type != NodeType.CONTAINER or not _photo_is_hero_full_bleed(photo):
        return hero
    hero_width = hero.sizing.width
    hero_height = hero.sizing.height
    if (
        hero_width is None
        or hero_height is None
        or float(hero_width) <= 0.0
        or float(hero_height) <= 0.0
    ):
        return hero
    width = round_geometry(float(hero_width))
    height = round_geometry(float(hero_height))
    photo_width = photo.sizing.width
    photo_height = photo.sizing.height
    placement = photo.stack_placement
    placement_top = float(placement.top) if placement is not None and placement.top is not None else 0.0
    drift = _HERO_PHOTO_VIEWPORT_DRIFT_PX
    needs_snap = (
        photo_width is None
        or photo_height is None
        or abs(float(photo_width) - width) >= drift
        or abs(float(photo_height) - height) >= drift
        or abs(placement_top) >= drift
    )
    if not needs_snap:
        return hero
    updated_photo = photo.model_copy(
        update={
            "sizing": photo.sizing.model_copy(update={"width": width, "height": height}),
        },
    )
    if placement is not None:
        updated_photo = updated_photo.model_copy(
            update={
                "stack_placement": placement.model_copy(
                    update={
                        "top": 0.0,
                        "left": 0.0,
                        "right": 0.0,
                        "bottom": 0.0,
                        "width": width,
                        "height": height,
                    },
                ),
            },
        )
    frame = photo.geometry_frame
    if frame is not None:
        layout = GeomRect(x=0.0, y=0.0, width=width, height=height)
        updated_photo = updated_photo.model_copy(
            update={
                "geometry_frame": frame.model_copy(
                    update={
                        "layout_rect": layout,
                        "intrinsic_size": layout,
                        "placement_aabb": layout,
                    },
                ),
            },
        )
    return hero.model_copy(update={"children": [updated_photo, *hero.children[1:]]})


def reconcile_product_hero_photo_viewport_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Align product-card hero rasters with their viewport aspect ratio before emit."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.CARD:
            return node
        from figma_flutter_agent.generator.layout.flex_policy.stack import (
            card_has_edge_to_edge_hero_stack,
        )

        if not card_has_edge_to_edge_hero_stack(node):
            return node
        hero = _reconcile_hero_photo_viewport(node.children[0])
        return node.model_copy(update={"children": [hero, *node.children[1:]]})

    return walk(root)

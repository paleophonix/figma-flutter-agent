"""Domain-specific layout reconcilers for clean design tree nodes."""

from __future__ import annotations

from figma_flutter_agent.parser.interaction import (
    WEEKDAY_CHIP_ROW_NAME,
    looks_like_checkbox_control,
    looks_like_weekday_chip_stack,
)
from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    SizingMode,
    StackPlacement,
)

from .placement import _infer_stack_child_top

_PROMO_CARD_MIN_WIDTH_PX = 120.0
_PROMO_CARD_MAX_WIDTH_PX = 400.0
_PROMO_CARD_MIN_HEIGHT_PX = 80.0
_PROMO_CARD_MAX_HEIGHT_PX = 260.0
_PROMO_CARD_ROW_TOP_SPREAD_PX = 56.0

_AUTH_PILL_ICON_MAX_LEFT_RATIO = 0.28
_AUTH_PILL_ICON_MAX_WIDTH_RATIO = 0.35
_AUTH_PILL_ICON_CENTER_TOLERANCE_PX = 4.0

_FLEX_LAYOUT_HOST_TYPES = frozenset(
    {
        NodeType.ROW,
        NodeType.COLUMN,
        NodeType.CONTAINER,
        NodeType.WRAP,
        NodeType.GRID,
    }
)

_CONSENT_ROW_MAX_TOP_GAP_PX = 12.0
_WEEKDAY_CHIP_ROW_MAX_TOP_GAP_PX = 12.0
_WEEKDAY_CHIP_ROW_MIN_COUNT = 5

_MIN_BRAND_WORDMARK_TOP_PX = 56.0
_CTA_SURFACE_FOOTER_GAP_PX = 4.0
_MIN_CTA_SURFACE_HEIGHT_PX = 32.0


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


def _is_auth_pill_container(node: CleanDesignTreeNode) -> bool:
    """Return True for full-width social/login pill rows (geometry only)."""
    from figma_flutter_agent.parser.geometry import (
        auth_button_confidence,
        social_auth_row_confidence,
    )

    return (
        auth_button_confidence(node) >= 0.5 or social_auth_row_confidence(node) >= 0.65
    )


def reconcile_auth_button_icon_placements_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Vertically center compact left icons inside auth pill stacks."""

    def patch_icon_placements(
        node: CleanDesignTreeNode,
        *,
        pill_height: float,
        pill_width: float,
    ) -> CleanDesignTreeNode:
        children = [
            patch_icon_placements(child, pill_height=pill_height, pill_width=pill_width)
            for child in node.children
        ]
        node = node.model_copy(update={"children": children})
        if node.type not in {NodeType.VECTOR, NodeType.IMAGE, NodeType.STACK}:
            return node
        if node.type == NodeType.STACK and not node.vector_asset_key:
            return node
        placement = node.stack_placement
        if placement is None:
            return node
        icon_height = (
            placement.height if placement.height is not None else node.sizing.height
        )
        icon_width = (
            placement.width if placement.width is not None else node.sizing.width
        )
        if icon_height is None or icon_width is None or icon_height <= 0:
            return node
        left = placement.left if placement.left is not None else node.offset_x
        if left is None or left > pill_width * _AUTH_PILL_ICON_MAX_LEFT_RATIO:
            return node
        if icon_width > pill_width * _AUTH_PILL_ICON_MAX_WIDTH_RATIO:
            return node
        current_top = _infer_stack_child_top(placement, parent_height=pill_height)
        if current_top is None:
            return node
        centered_top = (pill_height - float(icon_height)) / 2.0
        if (
            abs(float(current_top) - centered_top)
            <= _AUTH_PILL_ICON_CENTER_TOLERANCE_PX
        ):
            return node
        new_top = round_geometry(centered_top)
        if new_top is None:
            return node
        return node.model_copy(
            update={
                "stack_placement": placement.model_copy(
                    update={"top": new_top, "bottom": None},
                ),
            },
        )

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if not _is_auth_pill_container(node):
            return node
        pill_height = node.sizing.height
        pill_width = node.sizing.width
        if pill_height is None or pill_width is None or pill_height <= 0:
            return node
        return patch_icon_placements(
            node,
            pill_height=float(pill_height),
            pill_width=float(pill_width),
        )

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


def reconcile_consent_checkbox_rows_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Merge privacy/consent copy with a sibling checkbox into one positioned row."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        if node.type != NodeType.STACK:
            return node.model_copy(update={"children": children})
        consent_rows: list[CleanDesignTreeNode] = []
        consumed: set[str] = set()
        for child in children:
            if not looks_like_checkbox_control(child):
                continue
            checkbox_place = child.stack_placement
            if checkbox_place is None or checkbox_place.top is None:
                continue
            label_node: CleanDesignTreeNode | None = None
            for candidate in children:
                if candidate.type != NodeType.TEXT or candidate.id in consumed:
                    continue
                label_place = candidate.stack_placement
                if label_place is None or label_place.top is None:
                    continue
                if (
                    abs(float(label_place.top) - float(checkbox_place.top))
                    > _CONSENT_ROW_MAX_TOP_GAP_PX
                ):
                    continue
                label_left = float(label_place.left or 0.0)
                checkbox_left = float(checkbox_place.left or 0.0)
                if label_left >= checkbox_left:
                    continue
                label_node = candidate
                break
            if label_node is None:
                continue
            consumed.add(label_node.id)
            consumed.add(child.id)
            label_place = label_node.stack_placement
            assert label_place is not None
            row_left = float(label_place.left or 0.0)
            row_top = float(label_place.top or checkbox_place.top or 0.0)
            row_width = (
                float(checkbox_place.left or 0.0)
                + float(child.sizing.width or checkbox_place.width or 24.0)
                - row_left
            )
            row_height = max(
                float(label_place.height or label_node.sizing.height or 0.0),
                float(checkbox_place.height or child.sizing.height or 0.0),
            )
            row_place = label_place.model_copy(
                update={
                    "left": round_geometry(row_left),
                    "top": round_geometry(row_top),
                    "width": round_geometry(row_width),
                    "height": round_geometry(row_height),
                    "horizontal": "LEFT",
                    "vertical": "TOP",
                },
            )
            consent_rows.append(
                CleanDesignTreeNode(
                    id=f"{child.id}-consent-row",
                    name="ConsentRow",
                    type=NodeType.STACK,
                    sizing=node.sizing.model_copy(
                        update={
                            "width": row_width,
                            "height": row_height,
                        },
                    ),
                    stack_placement=row_place,
                    children=[label_node, child],
                ),
            )
        merged_children = [
            child for child in children if child.id not in consumed
        ] + consent_rows
        return node.model_copy(update={"children": merged_children})

    return walk(root)


def reconcile_weekday_chip_row_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Merge sibling weekday chip stacks into one interactive row node."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.STACK:
            return node
        chips = [child for child in children if looks_like_weekday_chip_stack(child)]
        if len(chips) < _WEEKDAY_CHIP_ROW_MIN_COUNT:
            return node
        tops = [
            float(chip.stack_placement.top)
            for chip in chips
            if chip.stack_placement is not None and chip.stack_placement.top is not None
        ]
        if tops and max(tops) - min(tops) > _WEEKDAY_CHIP_ROW_MAX_TOP_GAP_PX:
            return node
        consumed = {chip.id for chip in chips}
        lefts = [
            float(chip.stack_placement.left)
            for chip in chips
            if chip.stack_placement is not None
            and chip.stack_placement.left is not None
        ]
        rights = [
            float(chip.stack_placement.left or 0.0) + float(chip.sizing.width or 0.0)
            for chip in chips
            if chip.stack_placement is not None
        ]
        row_left = min(lefts) if lefts else 0.0
        row_top = min(tops) if tops else 0.0
        row_width = (
            max(rights) - row_left if rights else float(node.sizing.width or 0.0)
        )
        row_height = (
            max(float(chip.sizing.height or 0.0) for chip in chips) if chips else 0.0
        )
        row_place = StackPlacement(
            left=round_geometry(row_left),
            top=round_geometry(row_top),
            width=round_geometry(row_width),
            height=round_geometry(row_height),
            horizontal="LEFT",
            vertical="TOP",
        )
        row_node = CleanDesignTreeNode(
            id=f"weekday-row:{chips[0].id}",
            name=WEEKDAY_CHIP_ROW_NAME,
            type=NodeType.STACK,
            sizing=node.sizing.model_copy(
                update={
                    "width": row_width,
                    "height": row_height,
                },
            ),
            stack_placement=row_place,
            children=sorted(
                chips,
                key=lambda item: (
                    float(item.stack_placement.left or 0.0)
                    if item.stack_placement is not None
                    else 0.0
                ),
            ),
        )
        merged_children = [child for child in children if child.id not in consumed] + [
            row_node
        ]
        return node.model_copy(update={"children": merged_children})

    return walk(root)


def reconcile_title_subtitle_stacks_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Keep subtitle text below a larger title in the same absolute stack (music headers)."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.STACK or node.sizing.height is None:
            return node
        text_children = [
            child
            for child in node.children
            if child.type == NodeType.TEXT and child.stack_placement is not None
        ]
        if len(text_children) != 2:
            return node
        ordered = sorted(
            text_children,
            key=lambda item: float(item.style.font_size or 0),
            reverse=True,
        )
        title, subtitle = ordered[0], ordered[1]
        title_place = title.stack_placement
        subtitle_place = subtitle.stack_placement
        if title_place is None or subtitle_place is None:
            return node
        title_top = title_place.top if title_place.top is not None else 0.0
        title_height = title_place.height or title.sizing.height or 0.0
        subtitle_top = subtitle_place.top if subtitle_place.top is not None else 0.0
        min_subtitle_top = title_top + title_height + 4.0
        parent_width = float(node.sizing.width or node.stack_placement.width or 0.0)
        title_updates: dict[str, object] = {}
        if (
            title.style.text_align == "CENTER"
            and parent_width > 0
            and title_place.horizontal != "LEFT_RIGHT"
        ):
            title_updates = {
                "left": 0.0,
                "right": 0.0,
                "width": round_geometry(parent_width),
                "horizontal": "LEFT_RIGHT",
            }
        elif (
            title.style.text_align == "CENTER"
            and parent_width > 0
            and title_place.width is not None
            and float(title_place.width) > parent_width + 1.0
        ):
            title_updates = {
                "left": 0.0,
                "right": 0.0,
                "width": round_geometry(parent_width),
                "horizontal": "LEFT_RIGHT",
            }
        updates: dict[str, object] = {}
        if subtitle_top < min_subtitle_top - 0.5:
            updates["top"] = round_geometry(min_subtitle_top)
        subtitle_width = subtitle_place.width or subtitle.sizing.width or 0.0
        if (
            subtitle.style.text_align == "CENTER"
            and parent_width > 0
            and subtitle_width > 0
            and subtitle_width < parent_width - 8.0
        ):
            centered_left = (parent_width - subtitle_width) / 2.0
            current_left = (
                subtitle_place.left if subtitle_place.left is not None else 0.0
            )
            if abs(current_left - centered_left) > 2.0:
                updates["left"] = round_geometry(centered_left)
                updates["horizontal"] = "LEFT"
                updates["right"] = 0.0
        if not title_updates and not updates:
            return node
        new_subtitle_place = (
            subtitle_place.model_copy(update=updates) if updates else subtitle_place
        )
        new_title_place = (
            title_place.model_copy(update=title_updates)
            if title_updates
            else title_place
        )
        patched_children: list[CleanDesignTreeNode] = []
        for child in node.children:
            if child.id == subtitle.id:
                patched_children.append(
                    child.model_copy(update={"stack_placement": new_subtitle_place})
                )
            elif child.id == title.id:
                patched_children.append(
                    child.model_copy(update={"stack_placement": new_title_place})
                )
            else:
                patched_children.append(child)
        return node.model_copy(update={"children": patched_children})

    return walk(root)


def _is_top_centered_brand_mark(
    node: CleanDesignTreeNode,
    *,
    root_width: float,
) -> bool:
    """Compact centered logo row (flattened SVG or short stack) below the status-bar band."""
    placement = node.stack_placement
    if node.type != NodeType.STACK or placement is None:
        return False
    top = float(placement.top or 0.0)
    if top >= _MIN_BRAND_WORDMARK_TOP_PX:
        return False
    width = placement.width if placement.width is not None else node.sizing.width
    height = placement.height if placement.height is not None else node.sizing.height
    if width is None or height is None:
        return False
    if float(width) > 220.0 or float(height) > 48.0:
        return False
    if root_width <= 0:
        return False
    left = float(placement.left or 0.0)
    center_x = left + float(width) / 2.0
    if abs(center_x - root_width / 2.0) > 28.0:
        return False
    if node.render_boundary and node.vector_asset_key:
        return True
    return _is_brand_wordmark_stack(node)


def _is_brand_wordmark_stack(node: CleanDesignTreeNode) -> bool:
    """Three-across wordmark row (e.g. brand + icon + brand) pinned near the screen top."""
    if node.type != NodeType.STACK or len(node.children) != 3:
        return False
    texts = [child for child in node.children if child.type == NodeType.TEXT]
    if len(texts) != 2:
        return False
    width = node.sizing.width
    height = node.sizing.height
    placement = node.stack_placement
    if placement is not None:
        if placement.width is not None:
            width = placement.width
        if placement.height is not None:
            height = placement.height
    return (
        width is not None and height is not None and width <= 220.0 and height <= 48.0
    )


def reconcile_cta_footer_surfaces_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Move footer link rows below the full CTA pill instead of shrinking the fill height."""
    from figma_flutter_agent.parser.interaction import (
        _is_footer_link_text_node,
        _local_nodes,
        _stack_spans_primary_button_and_footer_link,
        primary_surface_node,
    )

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.STACK:
            return node
        text_nodes = [
            item
            for item in _local_nodes(node, 2)
            if item.type == NodeType.TEXT and item.text
        ]
        if not _stack_spans_primary_button_and_footer_link(node, text_nodes=text_nodes):
            return node
        surface = primary_surface_node(node)
        if surface is None:
            return node
        parent_height = float(node.sizing.height or 0)
        if parent_height <= 0:
            return node
        surface_placement = surface.stack_placement
        if surface_placement is None:
            return node
        surface_top = _infer_stack_child_top(
            surface_placement, parent_height=parent_height
        )
        if surface_top is None:
            return node
        surface_height = float(surface_placement.height or surface.sizing.height or 0)
        if surface_height < _MIN_CTA_SURFACE_HEIGHT_PX:
            surface_height = _MIN_CTA_SURFACE_HEIGHT_PX
        min_footer_top = surface_top + surface_height + _CTA_SURFACE_FOOTER_GAP_PX
        patched_children: list[CleanDesignTreeNode] = []
        stack_height = parent_height
        for child in node.children:
            if child.type != NodeType.TEXT or not _is_footer_link_text_node(child):
                patched_children.append(child)
                continue
            placement = child.stack_placement
            if placement is None or placement.top is None:
                patched_children.append(child)
                continue
            current_top = float(placement.top)
            if current_top + 0.5 >= min_footer_top:
                patched_children.append(child)
                continue
            footer_height = float(placement.height or child.sizing.height or 0)
            new_top = round_geometry(min_footer_top)
            if new_top is None:
                patched_children.append(child)
                continue
            patched_children.append(
                child.model_copy(
                    update={
                        "stack_placement": placement.model_copy(
                            update={"top": new_top}
                        ),
                    },
                ),
            )
            if footer_height > 0:
                stack_height = max(stack_height, float(new_top) + footer_height)
        if stack_height > parent_height + 0.5:
            node = node.model_copy(
                update={
                    "sizing": node.sizing.model_copy(update={"height": stack_height})
                },
            )
        return node.model_copy(update={"children": patched_children})

    return walk(root)


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


def reconcile_logo_wordmark_top_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Nudge top-pinned brand rows below the status-bar band on phone canvases."""

    root_width = float(root.sizing.width or 0.0)
    if root.stack_placement is not None and root.stack_placement.width is not None:
        root_width = float(root.stack_placement.width)

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children: list[CleanDesignTreeNode] = []
        for child in node.children:
            patched = walk(child)
            if node is root and _is_top_centered_brand_mark(
                patched, root_width=root_width
            ):
                placement = patched.stack_placement
                if (
                    placement is not None
                    and (placement.top or 0.0) < _MIN_BRAND_WORDMARK_TOP_PX
                ):
                    patched = patched.model_copy(
                        update={
                            "stack_placement": placement.model_copy(
                                update={
                                    "top": round_geometry(_MIN_BRAND_WORDMARK_TOP_PX)
                                },
                            ),
                        },
                    )
            children.append(patched)
        return node.model_copy(update={"children": children})

    return walk(root)


def reconcile_centered_text_placements_in_tree(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Horizontally center ``textAlign: CENTER`` labels inside absolute stacks."""

    def walk(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
        children = [walk(child) for child in node.children]
        node = node.model_copy(update={"children": children})
        if node.type != NodeType.STACK:
            return node
        parent_width = node.sizing.width
        if node.stack_placement is not None and node.stack_placement.width is not None:
            parent_width = node.stack_placement.width
        if parent_width is None or parent_width <= 0:
            return node
        patched_children: list[CleanDesignTreeNode] = []
        for child in node.children:
            if child.type != NodeType.TEXT or child.style.text_align != "CENTER":
                patched_children.append(child)
                continue
            placement = child.stack_placement
            if placement is not None and placement.horizontal == "LEFT_RIGHT":
                rounded_width = round_geometry(float(parent_width))
                text_width = float(parent_width)
                if child.sizing.width is not None:
                    text_width = min(float(child.sizing.width), float(parent_width))
                patched_children.append(
                    child.model_copy(
                        update={
                            "stack_placement": placement.model_copy(
                                update={
                                    "left": 0.0,
                                    "right": 0.0,
                                    "width": rounded_width,
                                    "horizontal": "LEFT_RIGHT",
                                },
                            ),
                            "sizing": child.sizing.model_copy(
                                update={
                                    "width": text_width,
                                    "width_mode": SizingMode.FIXED,
                                },
                            ),
                        },
                    ),
                )
                continue
            text_width = child.sizing.width
            if placement is None:
                patched_children.append(child)
                continue
            if placement.width is not None:
                text_width = placement.width
            if text_width is None or text_width <= 0:
                patched_children.append(child)
                continue
            if float(text_width) > float(parent_width):
                capped_width = round_geometry(float(parent_width))
                patched_children.append(
                    child.model_copy(
                        update={
                            "stack_placement": placement.model_copy(
                                update={
                                    "left": 0.0,
                                    "right": 0.0,
                                    "width": capped_width,
                                    "horizontal": "LEFT_RIGHT",
                                },
                            ),
                            "sizing": child.sizing.model_copy(
                                update={
                                    "width": float(parent_width),
                                    "width_mode": SizingMode.FIXED,
                                },
                            ),
                        },
                    ),
                )
                continue
            centered_left = (float(parent_width) - float(text_width)) / 2.0
            if centered_left < 0:
                patched_children.append(child)
                continue
            current_left = (
                placement.left if placement.left is not None else centered_left
            )
            if abs(current_left - centered_left) <= 2.0:
                patched_children.append(child)
                continue
            patched_children.append(
                child.model_copy(
                    update={
                        "stack_placement": placement.model_copy(
                            update={
                                "left": round_geometry(centered_left),
                                "horizontal": "LEFT",
                                "right": 0.0,
                            },
                        ),
                    },
                ),
            )
        return node.model_copy(update={"children": patched_children})

    return walk(root)


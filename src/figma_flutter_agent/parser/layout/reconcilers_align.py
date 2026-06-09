"""Stack alignment reconcilers: text centering, title/subtitle, brand wordmark."""

from __future__ import annotations

from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    SizingMode,
)

_MIN_BRAND_WORDMARK_TOP_PX = 56.0


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
        ) or (
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

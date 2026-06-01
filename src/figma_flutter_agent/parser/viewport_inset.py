"""Adjust Figma canvas Y coordinates for Flutter SafeArea / AppBar insets."""

from __future__ import annotations

from figma_flutter_agent.config import Settings
from figma_flutter_agent.parser.numeric_rounding import round_geometry
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def compute_viewport_top_inset_px(
    settings: Settings,
    root: CleanDesignTreeNode,
    *,
    use_scaffold: bool,
) -> float:
    """Return pixels to subtract from Figma ``top`` when mapping to Flutter body coords."""
    inset = 0.0
    responsive = settings.agent.responsive
    layout = settings.agent.layout
    if responsive.shell_safe_area or (
        responsive.enabled and root.type == NodeType.STACK and _is_phone_canvas(root)
    ):
        inset += responsive.status_bar_inset_px
    if use_scaffold and root.type != NodeType.STACK:
        inset += layout.app_bar_inset_px
    return inset


def _is_phone_canvas(root: CleanDesignTreeNode) -> bool:
    height = root.sizing.height
    width = root.sizing.width
    if height is None or width is None:
        return False
    return height >= 800.0 and 320.0 <= width <= 480.0


def apply_viewport_top_inset_to_tree(
    root: CleanDesignTreeNode,
    inset_px: float,
) -> None:
    """Subtract ``inset_px`` from TOP-pinned stack placements across the tree."""
    if inset_px <= 0:
        return

    def walk(node: CleanDesignTreeNode) -> None:
        placement = node.stack_placement
        if placement is not None and placement.vertical == "TOP":
            adjusted_top = max(0.0, placement.top - inset_px)
            if placement.top != adjusted_top:
                node.stack_placement = placement.model_copy(
                    update={"top": round_geometry(adjusted_top)},
                )
        for child in node.children:
            walk(child)

    walk(root)


def adjust_positioned_top_literal(top: float, inset_px: float) -> float:
    """Adjust one design-space ``top`` value for viewport inset."""
    if inset_px <= 0:
        return top
    return round_geometry(max(0.0, top - inset_px))

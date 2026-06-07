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
    """Subtract ``inset_px`` from TOP-pinned placements that are not stack-local.

    ``stack_placement.top`` on children of a ``STACK`` is measured from the stack
    origin, not the artboard. Applying the viewport inset to those nodes collapses
    vertical gaps (e.g. header at ``top: 0`` plus panel at ``top: 104`` both
    shift independently and overlap after inset).
    """
    if inset_px <= 0:
        return

    def walk(node: CleanDesignTreeNode, parent: CleanDesignTreeNode | None) -> None:
        placement = node.stack_placement
        if (
            placement is not None
            and placement.vertical == "TOP"
            and (parent is None or parent.type != NodeType.STACK)
        ):
            adjusted_top = max(0.0, placement.top - inset_px)
            if placement.top != adjusted_top:
                node.stack_placement = placement.model_copy(
                    update={"top": round_geometry(adjusted_top)},
                )
        for child in node.children:
            walk(child, node)

    walk(root, None)


def adjust_positioned_top_literal(top: float, inset_px: float) -> float:
    """Adjust one design-space ``top`` value for viewport inset."""
    if inset_px <= 0:
        return top
    return round_geometry(max(0.0, top - inset_px))

"""Screen-root IR kind recovery for mislabeled navigation hosts."""

from __future__ import annotations

from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)

SCREEN_ROOT_NAV_DOCK_MAX_HEIGHT_PX = 160.0
SCREEN_ROOT_NAV_DOCK_MAX_CHILD_COUNT = 12


def nav_bottom_bar_kind_contradicts_clean_node(node: CleanDesignTreeNode) -> bool:
    """Return True when ``nav_bottom_bar`` IR kind cannot own ``node``."""
    height = node.sizing.height
    if height is not None and float(height) > SCREEN_ROOT_NAV_DOCK_MAX_HEIGHT_PX:
        return True
    return node.type != NodeType.BOTTOM_NAV and len(node.children) > SCREEN_ROOT_NAV_DOCK_MAX_CHILD_COUNT


def downgrade_nav_bottom_bar_ir_node(
    ir_node: WidgetIrNode,
    clean_node: CleanDesignTreeNode,
) -> WidgetIrNode:
    """Downgrade a mislabeled ``nav_bottom_bar`` IR node to a layout kind."""
    if ir_node.kind != WidgetIrKind.NAV_BOTTOM_BAR:
        return ir_node
    if not nav_bottom_bar_kind_contradicts_clean_node(clean_node):
        return ir_node
    if clean_node.type in {NodeType.STACK, NodeType.COLUMN, NodeType.ROW, NodeType.WRAP}:
        replacement = WidgetIrKind.STACK
    else:
        replacement = WidgetIrKind.AUTO
    return ir_node.model_copy(update={"kind": replacement})


def heal_screen_root_nav_bottom_bar_kind(
    screen_ir: ScreenIr,
    clean_root: CleanDesignTreeNode,
) -> bool:
    """Apply ScreenRootNavKindDowngradeLaw to the screen IR root when needed.

    Returns:
        True when the root kind was downgraded.
    """
    healed = downgrade_nav_bottom_bar_ir_node(screen_ir.root, clean_root)
    if healed is screen_ir.root:
        return False
    screen_ir.root = healed
    return True

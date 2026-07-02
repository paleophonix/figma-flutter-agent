"""Screen-root IR kind recovery for mislabeled navigation and control hosts."""

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

SCREEN_ROOT_FORBIDDEN_CONTROL_KINDS: frozenset[WidgetIrKind] = frozenset(
    {
        WidgetIrKind.INPUT_RATING,
        WidgetIrKind.INPUT_SEARCH_BAR,
        WidgetIrKind.INPUT_DROPDOWN,
        WidgetIrKind.INPUT_PICKER_DATE,
        WidgetIrKind.INPUT_PICKER_TIME,
        WidgetIrKind.INPUT_STEPPER,
        WidgetIrKind.INPUT_SLIDER,
        WidgetIrKind.INPUT_FILE_UPLOADER,
        WidgetIrKind.CONTROL_CHECKBOX,
        WidgetIrKind.CONTROL_RADIO,
        WidgetIrKind.CONTROL_SWITCH,
        WidgetIrKind.CONTROL_SEGMENTED,
        WidgetIrKind.NAV_BOTTOM_BAR,
        WidgetIrKind.NAV_APP_BAR,
        WidgetIrKind.NAV_TAB_BAR,
        WidgetIrKind.NAV_DRAWER,
        WidgetIrKind.NAV_STEPPER,
        WidgetIrKind.NAV_PAGINATION,
    }
)


def screen_root_kind_contradicts_clean_node(
    ir_kind: WidgetIrKind,
    node: CleanDesignTreeNode,
) -> bool:
    """Return True when ``ir_kind`` cannot own a screen-sized clean-tree root."""
    if ir_kind not in SCREEN_ROOT_FORBIDDEN_CONTROL_KINDS:
        return False
    height = node.sizing.height
    if height is not None and float(height) > SCREEN_ROOT_NAV_DOCK_MAX_HEIGHT_PX:
        return True
    if ir_kind == WidgetIrKind.NAV_BOTTOM_BAR and node.type == NodeType.BOTTOM_NAV:
        return False
    return node.type != NodeType.BOTTOM_NAV and len(node.children) > SCREEN_ROOT_NAV_DOCK_MAX_CHILD_COUNT


def nav_bottom_bar_kind_contradicts_clean_node(node: CleanDesignTreeNode) -> bool:
    """Return True when ``nav_bottom_bar`` IR kind cannot own ``node``."""
    return screen_root_kind_contradicts_clean_node(WidgetIrKind.NAV_BOTTOM_BAR, node)


def _downgrade_screen_root_ir_kind(
    ir_node: WidgetIrNode,
    clean_node: CleanDesignTreeNode,
) -> WidgetIrNode:
    """Downgrade a mislabeled screen-root IR node to a layout kind."""
    if not screen_root_kind_contradicts_clean_node(ir_node.kind, clean_node):
        return ir_node
    if clean_node.type in {NodeType.STACK, NodeType.COLUMN, NodeType.ROW, NodeType.WRAP}:
        replacement = WidgetIrKind.STACK
    else:
        replacement = WidgetIrKind.AUTO
    return ir_node.model_copy(update={"kind": replacement})


def downgrade_nav_bottom_bar_ir_node(
    ir_node: WidgetIrNode,
    clean_node: CleanDesignTreeNode,
) -> WidgetIrNode:
    """Downgrade a mislabeled ``nav_bottom_bar`` IR node to a layout kind."""
    if ir_node.kind != WidgetIrKind.NAV_BOTTOM_BAR:
        return ir_node
    return _downgrade_screen_root_ir_kind(ir_node, clean_node)


def heal_screen_root_control_kind(
    screen_ir: ScreenIr,
    clean_root: CleanDesignTreeNode,
) -> bool:
    """Apply ScreenRootControlKindVetoLaw to the screen IR root when needed.

    Returns:
        True when the root kind was downgraded.
    """
    healed = _downgrade_screen_root_ir_kind(screen_ir.root, clean_root)
    if healed is screen_ir.root:
        return False
    screen_ir.root = healed
    return True


def heal_screen_root_nav_bottom_bar_kind(
    screen_ir: ScreenIr,
    clean_root: CleanDesignTreeNode,
) -> bool:
    """Apply ScreenRootNavKindDowngradeLaw to the screen IR root when needed.

    Returns:
        True when the root kind was downgraded.
    """
    return heal_screen_root_control_kind(screen_ir, clean_root)

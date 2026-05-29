"""Figma clean-tree → Flutter flex wrap policy (constraints down, sizes up)."""

from __future__ import annotations

from enum import StrEnum

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode


class FlexWrapKind(StrEnum):
    """How to wrap a flex child before it is emitted or reconciled."""

    NONE = "none"
    EXPANDED = "expanded"
    FLEXIBLE_LOOSE = "flexible_loose"
    SIZED_BOX_WIDTH = "sized_box_width"


_FLEX_RIGID_CHILD_TYPES = frozenset(
    {
        NodeType.TEXT,
        NodeType.CONTAINER,
        NodeType.IMAGE,
        NodeType.VECTOR,
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CARD,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.DROPDOWN,
    }
)


def resolve_flex_wrap(
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> FlexWrapKind:
    """Return the flex wrapper required for ``node`` under ``parent_type``."""
    if parent_type is None:
        return FlexWrapKind.NONE

    width_mode = node.sizing.width_mode
    height_mode = node.sizing.height_mode

    if parent_type == NodeType.ROW:
        if width_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if width_mode in {SizingMode.FIXED, SizingMode.HUG} and node.type in _FLEX_RIGID_CHILD_TYPES:
            return FlexWrapKind.FLEXIBLE_LOOSE

    if parent_type == NodeType.COLUMN:
        if height_mode == SizingMode.FILL:
            return FlexWrapKind.EXPANDED
        if width_mode == SizingMode.FILL:
            return FlexWrapKind.SIZED_BOX_WIDTH

    return FlexWrapKind.NONE


def apply_flex_wrap_to_widget(
    widget: str,
    *,
    parent_type: NodeType | None,
    node: CleanDesignTreeNode,
) -> str:
    """Wrap a rendered widget expression according to flex policy."""
    kind = resolve_flex_wrap(parent_type=parent_type, node=node)
    if kind == FlexWrapKind.NONE:
        return widget
    if kind == FlexWrapKind.EXPANDED:
        return f"Expanded(child: {widget})"
    if kind == FlexWrapKind.FLEXIBLE_LOOSE:
        return f"Flexible(fit: FlexFit.loose, child: {widget})"
    if kind == FlexWrapKind.SIZED_BOX_WIDTH:
        return f"SizedBox(width: double.infinity, child: {widget})"
    return widget

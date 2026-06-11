"""Macro scroll host injection pass."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes.geometry import root_vertical_extent
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    SizingMode,
    WidgetIrKind,
    WidgetIrLayoutHints,
    WidgetIrNode,
)

_SCROLL_HOST_TYPES = frozenset({NodeType.COLUMN, NodeType.STACK})


def _should_inject_scroll_host(
    node: CleanDesignTreeNode,
    *,
    threshold_px: int,
) -> bool:
    extent = root_vertical_extent(node)
    return extent > float(threshold_px)


def _already_scroll_host_clean(node: CleanDesignTreeNode) -> bool:
    return node.scroll_axis == "vertical" and node.sizing.height_mode == SizingMode.HUG


def _already_scroll_host_ir(node: WidgetIrNode) -> bool:
    return node.kind == WidgetIrKind.NAV_SCROLL_HOST


def _apply_scroll_host_clean(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    sizing_updates: dict[str, object] = {"height_mode": SizingMode.HUG}
    if node.type == NodeType.COLUMN:
        sizing_updates["height"] = None
    sizing = node.sizing.model_copy(update=sizing_updates)
    return node.model_copy(
        update={
            "scroll_axis": "vertical",
            "sizing": sizing,
        },
    )


def _apply_scroll_host_ir(node: WidgetIrNode) -> WidgetIrNode:
    hints = WidgetIrLayoutHints(scroll_axis="vertical")
    return node.model_copy(
        update={
            "kind": WidgetIrKind.NAV_SCROLL_HOST,
            "layout_hints": hints,
        },
    )


def inject_scroll_host(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    macro_height_threshold_px: int,
    inject_at_root: bool = False,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Wrap tall roots in vertical scroll semantics on both graphs."""
    if not inject_at_root:
        return screen_ir, clean_tree
    if clean_tree.type not in _SCROLL_HOST_TYPES:
        return screen_ir, clean_tree
    if _already_scroll_host_clean(clean_tree) and _already_scroll_host_ir(screen_ir.root):
        return screen_ir, clean_tree
    if not _should_inject_scroll_host(
        clean_tree,
        threshold_px=macro_height_threshold_px,
    ):
        return screen_ir, clean_tree

    updated_clean = _apply_scroll_host_clean(clean_tree)
    updated_ir = screen_ir.model_copy(
        update={
            "root": _apply_scroll_host_ir(screen_ir.root),
        },
    )
    return updated_ir, updated_clean

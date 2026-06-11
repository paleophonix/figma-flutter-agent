"""Macro scroll host injection pass."""

from __future__ import annotations

from figma_flutter_agent.generator.artboard import resolve_artboard_height
from figma_flutter_agent.generator.ir.passes.layout_criteria import evaluate_scroll_host
from figma_flutter_agent.generator.ir.passes.protocol import PassContext
from figma_flutter_agent.generator.ir.passes.provenance_record import record_node_mutation
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
    ctx: PassContext | None = None,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Wrap tall roots in vertical scroll semantics on both graphs."""
    if not inject_at_root:
        return screen_ir, clean_tree
    if clean_tree.type not in _SCROLL_HOST_TYPES:
        return screen_ir, clean_tree
    if _already_scroll_host_clean(clean_tree) and _already_scroll_host_ir(screen_ir.root):
        return screen_ir, clean_tree

    artboard_height = resolve_artboard_height(clean_tree)
    decision = evaluate_scroll_host(
        clean_tree,
        artboard_height=artboard_height,
        fallback_threshold_px=macro_height_threshold_px,
    )
    if not decision.activated:
        return screen_ir, clean_tree

    policy = None if artboard_height is not None else "artboard_unknown"
    before = clean_tree
    updated_clean = _apply_scroll_host_clean(clean_tree)
    updated_ir = screen_ir.model_copy(
        update={
            "root": _apply_scroll_host_ir(screen_ir.root),
        },
    )
    if ctx is not None:
        record_node_mutation(
            ctx,
            transform="scroll_host",
            node_id=clean_tree.id,
            field_name="scroll_axis",
            old=before.scroll_axis,
            new=updated_clean.scroll_axis,
            policy=policy,
        )
        record_node_mutation(
            ctx,
            transform="scroll_host",
            node_id=clean_tree.id,
            field_name="sizing.height_mode",
            old=before.sizing.height_mode.value,
            new=updated_clean.sizing.height_mode.value,
        )
        record_node_mutation(
            ctx,
            transform="scroll_host",
            node_id=clean_tree.id,
            field_name="kind",
            old=screen_ir.root.kind.value,
            new=WidgetIrKind.NAV_SCROLL_HOST.value,
            policy=policy,
        )
    return updated_ir, updated_clean

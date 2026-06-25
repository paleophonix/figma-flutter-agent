"""Themed primitive emit for semantic nodes without native template proof."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext, render_kwargs
from figma_flutter_agent.generator.layout.widgets.emit.shell import render_leaf_body
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrKind, WidgetIrNode

_FILLED_BUTTON_KINDS = frozenset(
    {
        WidgetIrKind.BUTTON_FILLED,
        WidgetIrKind.BUTTON,
    }
)
_OUTLINED_BUTTON_KINDS = frozenset(
    {
        WidgetIrKind.BUTTON_OUTLINED,
        WidgetIrKind.BUTTON_TEXT,
        WidgetIrKind.BUTTON_ICON,
    }
)


def _first_text_label(node: CleanDesignTreeNode) -> str | None:
    if node.type == NodeType.TEXT and node.text:
        return node.text
    for child in node.children:
        label = _first_text_label(child)
        if label is not None:
            return label
    return None


def _emit_themed_text(label: str, *, on_primary: bool) -> str:
    color = (
        "Theme.of(context).colorScheme.onPrimary"
        if on_primary
        else "Theme.of(context).colorScheme.onSurface"
    )
    escaped = label.replace("\\", "\\\\").replace("'", "\\'")
    return (
        f"Text('{escaped}', "
        f"style: Theme.of(context).textTheme.labelLarge?.copyWith(color: {color}))"
    )


def _shell_for_kind(kind: WidgetIrKind, inner: str) -> str:
    if kind in _FILLED_BUTTON_KINDS:
        return (
            "DecoratedBox("
            "decoration: BoxDecoration("
            "color: Theme.of(context).colorScheme.primary, "
            "borderRadius: BorderRadius.circular(8)), "
            f"child: Padding(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12), "
            f"child: {inner}))"
        )
    if kind in _OUTLINED_BUTTON_KINDS:
        return (
            "DecoratedBox("
            "decoration: BoxDecoration("
            "border: Border.all(color: Theme.of(context).colorScheme.outline), "
            "borderRadius: BorderRadius.circular(8)), "
            f"child: Padding(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12), "
            f"child: {inner}))"
        )
    if kind == WidgetIrKind.CHIP_CHOICE:
        return (
            "DecoratedBox("
            "decoration: BoxDecoration("
            "color: Theme.of(context).colorScheme.secondaryContainer, "
            "borderRadius: BorderRadius.circular(16)), "
            f"child: Padding(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6), "
            f"child: {inner}))"
        )
    if kind == WidgetIrKind.INPUT_TEXT_FIELD:
        return (
            "DecoratedBox("
            "decoration: BoxDecoration("
            "color: Theme.of(context).colorScheme.surface, "
            "border: Border.all(color: Theme.of(context).colorScheme.outline), "
            "borderRadius: BorderRadius.circular(8)), "
            f"child: Padding(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10), "
            f"child: {inner}))"
        )
    if kind in {WidgetIrKind.CONTAINER_CARD, WidgetIrKind.CONTAINER_LIST_TILE}:
        return (
            "Material("
            "color: Theme.of(context).colorScheme.surfaceContainerLow, "
            "borderRadius: BorderRadius.circular(12), "
            f"child: {inner})"
        )
    return (
        "DecoratedBox("
        "decoration: BoxDecoration("
        "color: Theme.of(context).colorScheme.surface, "
        "borderRadius: BorderRadius.circular(8)), "
        f"child: {inner})"
    )


def emit_styled_primitive(
    ir: WidgetIrNode,
    *,
    clean: CleanDesignTreeNode,
    ctx: IrEmitContext,
) -> str:
    """Emit a themed Flutter primitive shell for a semantic IR node."""
    label = _first_text_label(clean)
    if label is not None and ir.kind in _FILLED_BUTTON_KINDS | _OUTLINED_BUTTON_KINDS | {
        WidgetIrKind.CHIP_CHOICE
    }:
        inner = _emit_themed_text(
            label,
            on_primary=ir.kind in _FILLED_BUTTON_KINDS,
        )
    else:
        inner = render_leaf_body(
            clean,
            is_layout_root=False,
            **render_kwargs(ctx),
        )
    if ir.kind == WidgetIrKind.CONTAINER_CARD:
        from figma_flutter_agent.generator.layout.widgets.emit.containers import (
            card_should_emit_as_overlay_stack,
        )

        if card_should_emit_as_overlay_stack(clean):
            return inner
    return _shell_for_kind(ir.kind, inner)

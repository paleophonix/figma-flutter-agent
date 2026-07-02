"""Emit tab switcher chrome: row band + bottom-anchored decor layers."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets.layout import _positioned_fields
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def emit_tab_switcher_stack_children(
    node: CleanDesignTreeNode,
    *,
    emitted_pairs: list[tuple[CleanDesignTreeNode, str]],
) -> str:
    """Compose tab labels in a full-bleed row with decor pinned above the baseline.

    Args:
        node: Tab switcher stack host.
        emitted_pairs: Pre-rendered (child, widget) pairs for emitted stack children only.

    Returns:
        Dart ``Stack`` widget expression for the tab switcher chrome.
    """
    tab_pairs = [(child, widget) for child, widget in emitted_pairs if child.type == NodeType.TEXT]
    decor_pairs = [
        (child, widget) for child, widget in emitted_pairs if child.type != NodeType.TEXT
    ]
    tab_cells = [f"Expanded(child: {widget})" for _, widget in tab_pairs]
    row_widget = (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [{', '.join(tab_cells) or 'const SizedBox.shrink()'}]"
        ")"
    )
    row_widget = f"Positioned(left: 0.0, right: 0.0, top: 0.0, bottom: 0.0, child: {row_widget})"
    decor_widgets: list[str] = []
    for child, widget in decor_pairs:
        placement = child.stack_placement
        if placement is None:
            decor_widgets.append(widget)
            continue
        fields = _positioned_fields(placement)
        if not fields:
            decor_widgets.append(widget)
            continue
        decor_widgets.append(f"Positioned({', '.join(fields)}, child: {widget})")
    chrome_children = [row_widget, *decor_widgets]
    return (
        "Stack(clipBehavior: Clip.none, "
        f"children: [{', '.join(chrome_children) or 'const SizedBox.shrink()'}]"
        ")"
    )

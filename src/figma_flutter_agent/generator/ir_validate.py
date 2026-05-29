"""Validate screen IR against a clean design tree before Dart emission."""

from __future__ import annotations

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir_tree import index_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ExtractedWidget,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)


def _walk_ir(node: WidgetIrNode) -> list[WidgetIrNode]:
    nodes = [node]
    for child in node.children:
        nodes.extend(_walk_ir(child))
    return nodes


def validate_screen_ir(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None = None,
) -> None:
    """Raise ``GenerationError`` when IR references unknown or invalid nodes."""
    tree_by_id = index_clean_tree(root)
    omit = frozenset(screen_ir.omit_figma_ids)
    extracted = extracted_widget_names or frozenset()

    if screen_ir.root.figma_id not in tree_by_id:
        raise GenerationError(f"screenIr.root figmaId {screen_ir.root.figma_id!r} not in clean tree")
    if screen_ir.root.figma_id in omit:
        raise GenerationError("screenIr.root cannot appear in omitFigmaIds")

    for ir_node in _walk_ir(screen_ir.root):
        if ir_node.figma_id not in tree_by_id:
            raise GenerationError(f"screenIr figmaId {ir_node.figma_id!r} not in clean tree")
        if ir_node.figma_id in omit:
            raise GenerationError(f"screenIr node {ir_node.figma_id!r} is listed in omitFigmaIds")
        clean = tree_by_id[ir_node.figma_id]
        if ir_node.kind == WidgetIrKind.EXTRACTED:
            if ir_node.ref is None or not ir_node.ref.widget_name.strip():
                raise GenerationError(
                    f"screenIr node {ir_node.figma_id!r} kind=extracted requires ref.widgetName"
                )
            if extracted and ir_node.ref.widget_name not in extracted:
                raise GenerationError(
                    f"extracted widget {ir_node.ref.widget_name!r} not in extractedWidgets"
                )
            if ir_node.children:
                raise GenerationError(
                    f"screenIr node {ir_node.figma_id!r} kind=extracted must not have children"
                )
        child_ids = {child.id for child in clean.children}
        for ir_child in ir_node.children:
            if ir_child.figma_id not in child_ids:
                raise GenerationError(
                    f"screenIr child {ir_child.figma_id!r} is not a child of {ir_node.figma_id!r} "
                    "in cleanTree"
                )
        placement = clean.stack_placement
        if placement is not None:
            parent_ir = _find_parent_ir(screen_ir.root, ir_node.figma_id)
            if parent_ir is not None:
                parent_clean = tree_by_id.get(parent_ir.figma_id)
                if parent_clean is not None and parent_clean.type != NodeType.STACK:
                    raise GenerationError(
                        f"node {ir_node.figma_id!r} has stackPlacement but IR parent "
                        f"{parent_ir.figma_id!r} is not STACK"
                    )


def validate_extracted_widget_ir(
    widget: ExtractedWidget,
    root: CleanDesignTreeNode,
) -> None:
    """Raise when an extracted widget IR subtree is invalid against ``root``."""
    if widget.widget_ir is None:
        return
    tree_by_id = index_clean_tree(root)
    if widget.widget_ir.figma_id not in tree_by_id:
        raise GenerationError(
            f"extractedWidgets {widget.widget_name!r} widgetIr figmaId "
            f"{widget.widget_ir.figma_id!r} not in clean tree"
        )
    validate_screen_ir(
        ScreenIr(root=widget.widget_ir),
        root,
        extracted_widget_names=frozenset({widget.widget_name}),
    )


def validate_extracted_widgets(
    widgets: list[ExtractedWidget],
    root: CleanDesignTreeNode,
) -> None:
    for widget in widgets:
        validate_extracted_widget_ir(widget, root)


def _find_parent_ir(node: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    for child in node.children:
        if child.figma_id == figma_id:
            return node
        found = _find_parent_ir(child, figma_id)
        if found is not None:
            return found
    return None

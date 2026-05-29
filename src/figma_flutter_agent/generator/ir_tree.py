"""Clean-tree indexing and IR merge helpers."""

from __future__ import annotations

from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrOverrides,
)


def index_clean_tree(root: CleanDesignTreeNode) -> dict[str, CleanDesignTreeNode]:
    """Map Figma node id → clean-tree node for the full subtree."""
    indexed: dict[str, CleanDesignTreeNode] = {}

    def walk(node: CleanDesignTreeNode) -> None:
        indexed[node.id] = node
        for child in node.children:
            walk(child)

    walk(root)
    return indexed


def default_screen_ir(root: CleanDesignTreeNode) -> ScreenIr:
    """Build identity IR that mirrors the clean design tree."""

    def walk(node: CleanDesignTreeNode) -> WidgetIrNode:
        return WidgetIrNode(
            figma_id=node.id,
            kind=WidgetIrKind.AUTO,
            children=[walk(child) for child in node.children],
        )

    return ScreenIr(root=walk(root))


def _apply_ir_overrides(
    node: CleanDesignTreeNode,
    overrides: WidgetIrOverrides | None,
) -> CleanDesignTreeNode:
    if overrides is None:
        return node
    updates: dict[str, object] = {}
    if overrides.text is not None:
        updates["text"] = overrides.text
    if overrides.accessibility_label is not None:
        updates["accessibility_label"] = overrides.accessibility_label
    if not updates:
        return node
    return node.model_copy(update=updates)


def merge_ir_node(
    clean: CleanDesignTreeNode,
    ir: WidgetIrNode,
    *,
    omit_ids: frozenset[str],
    extracted_class_by_widget_name: dict[str, str] | None = None,
) -> CleanDesignTreeNode:
    """Apply IR child ordering/filtering onto a clean-tree node."""
    merged = _apply_ir_overrides(clean, ir.overrides)
    if clean.id in omit_ids:
        return merged.model_copy(update={"children": []})
    if ir.kind == WidgetIrKind.EXTRACTED:
        ref_name = (ir.ref.widget_name if ir.ref else "").strip()
        class_name = ref_name
        if ref_name and extracted_class_by_widget_name:
            class_name = extracted_class_by_widget_name.get(ref_name, ref_name)
        return merged.model_copy(
            update={
                "children": [],
                "extracted_widget_ref": class_name or None,
            },
        )
    if not ir.children:
        return merged
    clean_child_by_id = {child.id: child for child in clean.children}
    merged_children: list[CleanDesignTreeNode] = []
    for ir_child in ir.children:
        if ir_child.figma_id in omit_ids:
            continue
        clean_child = clean_child_by_id.get(ir_child.figma_id)
        if clean_child is None:
            continue
        merged_children.append(
            merge_ir_node(
                clean_child,
                ir_child,
                omit_ids=omit_ids,
                extracted_class_by_widget_name=extracted_class_by_widget_name,
            )
        )
    return merged.model_copy(update={"children": merged_children})


def merge_screen_ir(
    root: CleanDesignTreeNode,
    screen_ir: ScreenIr,
    *,
    extracted_class_by_widget_name: dict[str, str] | None = None,
) -> CleanDesignTreeNode:
    """Return a clean tree with ``screen_ir`` structure applied at ``root``."""
    omit_ids = frozenset(screen_ir.omit_figma_ids)
    merged = merge_ir_node(
        root,
        screen_ir.root,
        omit_ids=omit_ids,
        extracted_class_by_widget_name=extracted_class_by_widget_name,
    )
    if screen_ir.stack_child_order and merged.type.value == "STACK":
        order = screen_ir.stack_child_order
        by_id = {child.id: child for child in merged.children}
        ordered = [by_id[node_id] for node_id in order if node_id in by_id]
        tail = [child for child in merged.children if child.id not in frozenset(order)]
        merged = merged.model_copy(update={"children": [*ordered, *tail]})
    return merged

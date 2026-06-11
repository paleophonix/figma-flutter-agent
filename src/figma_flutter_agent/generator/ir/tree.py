"""Clean-tree indexing and IR merge helpers."""

from __future__ import annotations

from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrOverrides,
)


def validate_unique_node_ids(root: CleanDesignTreeNode) -> None:
    """Fail fast when duplicate Figma node ids appear in the clean tree."""
    from figma_flutter_agent.errors import GenerationError

    seen: dict[str, str] = {}

    def walk(node: CleanDesignTreeNode, path: str) -> None:
        prior = seen.get(node.id)
        if prior is not None:
            raise GenerationError(
                f"duplicate node id {node.id!r} at {path} and {prior}"
            )
        seen[node.id] = path
        for child in node.children:
            walk(child, f"{path}/{child.id}")

    walk(root, root.id)


def index_clean_tree(root: CleanDesignTreeNode) -> dict[str, CleanDesignTreeNode]:
    """Map Figma node id → clean-tree node for the full subtree."""
    validate_unique_node_ids(root)
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
    style_updates: dict[str, object] = {}
    if overrides.text is not None:
        updates["text"] = overrides.text
    if overrides.accessibility_label is not None:
        updates["accessibility_label"] = overrides.accessibility_label
    if overrides.text_color is not None:
        style_updates["text_color"] = overrides.text_color
    if overrides.background_color is not None:
        style_updates["background_color"] = overrides.background_color
    if overrides.font_size is not None:
        style_updates["font_size"] = overrides.font_size
    if style_updates:
        updates["style"] = node.style.model_copy(update=style_updates)
    if not updates:
        return node
    return node.model_copy(update=updates)


_FLOW_LAYOUT_PARENT_TYPES = frozenset(
    {NodeType.COLUMN, NodeType.ROW, NodeType.INPUT, NodeType.CARD},
)
_FLOW_OMITTED_CHILD_PRESERVE_TYPES = frozenset(
    {
        NodeType.STACK,
        NodeType.COLUMN,
        NodeType.ROW,
        NodeType.TEXT,
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.CARD,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
    }
)


def preserve_clean_child_without_ir(clean: CleanDesignTreeNode) -> bool:
    """Stack-placed visuals omitted from screen IR still render from the clean tree."""
    if clean.stack_placement is None:
        return False
    if clean.type in {NodeType.VECTOR, NodeType.IMAGE, NodeType.STACK}:
        return True
    if clean.type == NodeType.CONTAINER:
        from figma_flutter_agent.generator.ir.presence.stack import (
            container_requires_stack_visual_ir,
        )

        return container_requires_stack_visual_ir(clean)
    return False


def preserve_clean_child_omitted_from_partial_ir(
    clean_child: CleanDesignTreeNode,
    clean_parent: CleanDesignTreeNode,
) -> bool:
    """Keep flow-layout sections (headline, CTA) when the LLM IR subtree is incomplete."""
    if preserve_clean_child_without_ir(clean_child):
        return True
    if clean_parent.type not in _FLOW_LAYOUT_PARENT_TYPES:
        return False
    return clean_child.type in _FLOW_OMITTED_CHILD_PRESERVE_TYPES


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
        if clean.type == NodeType.STACK and clean.children:
            preserved = [child for child in clean.children if child.id not in omit_ids]
            return merged.model_copy(update={"children": preserved})
        return merged
    clean_child_by_id = {child.id: child for child in clean.children}
    merged_children: list[CleanDesignTreeNode] = []
    emitted_ids: set[str] = set()
    for ir_child in ir.children:
        clean_child = clean_child_by_id.get(ir_child.figma_id)
        if clean_child is None or clean_child.id in omit_ids:
            continue
        emitted_ids.add(clean_child.id)
        merged_children.append(
            merge_ir_node(
                clean_child,
                ir_child,
                omit_ids=omit_ids,
                extracted_class_by_widget_name=extracted_class_by_widget_name,
            )
        )
    for clean_child in clean.children:
        if clean_child.id in omit_ids or clean_child.id in emitted_ids:
            continue
        if preserve_clean_child_without_ir(
            clean_child
        ) or preserve_clean_child_omitted_from_partial_ir(clean_child, merged):
            merged_children.append(clean_child)
    return merged.model_copy(update={"children": merged_children})


def merge_partial_stack_child_order(
    clean: list[str],
    partial: list[str],
) -> list[str]:
    """Merge a partial child-order list with the canonical clean-tree order.

    Items present in *partial* keep their relative order from *partial*.
    Items in *clean* but missing from *partial* are inserted at the position
    immediately before the first *partial* item whose clean-tree index is
    greater than the missing item's.

    Args:
        clean: Canonical child id order from the clean design tree.
        partial: Subset of ids in the LLM-provided order.

    Returns:
        Merged list containing all ids from *clean* that appear in *partial*
        (in partial's order), with missing items spliced in at the correct
        relative positions.
    """
    clean_index: dict[str, int] = {id_: i for i, id_ in enumerate(clean)}
    partial_set = set(partial)
    result = list(partial)
    for id_ in clean:
        if id_ in partial_set:
            continue
        ci = clean_index[id_]
        insert_pos = len(result)
        for j, existing in enumerate(result):
            if clean_index.get(existing, float("inf")) > ci:
                insert_pos = j
                break
        result.insert(insert_pos, id_)
    return result


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
        by_id = {child.id: child for child in merged.children}
        clean_order = [child.id for child in root.children if child.id in by_id]
        merged_order = merge_partial_stack_child_order(clean_order, screen_ir.stack_child_order)
        reordered = [by_id[node_id] for node_id in merged_order if node_id in by_id]
        merged = merged.model_copy(update={"children": reordered})
    return merged

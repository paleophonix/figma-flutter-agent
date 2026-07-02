"""Clean-tree indexing and IR merge helpers."""

from __future__ import annotations

from loguru import logger

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
            raise GenerationError(f"duplicate node id {node.id!r} at {path} and {prior}")
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


def index_ir_tree(root: WidgetIrNode) -> dict[str, WidgetIrNode]:
    """Map Figma node id → IR node for the full screen IR subtree."""
    indexed: dict[str, WidgetIrNode] = {}

    def walk(node: WidgetIrNode) -> None:
        indexed[node.figma_id] = node
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


_CHECKPOINT_A1_MERGE = "A1_merge"
_TRANSFORM_IR_OVERRIDE = "ir_override"


def _record_override_mutation(
    *,
    node_id: str,
    field: str,
    old: object,
    new: object,
) -> None:
    from figma_flutter_agent.debug.provenance import get_provenance_recorder

    recorder = get_provenance_recorder()
    if recorder is None:
        return
    recorder.record_mutation(
        checkpoint=_CHECKPOINT_A1_MERGE,
        transform=_TRANSFORM_IR_OVERRIDE,
        node_id=node_id,
        field=field,
        old=old,
        new=new,
        policy="llm_proposal_commit",
    )


def _apply_ir_overrides(
    node: CleanDesignTreeNode,
    overrides: WidgetIrOverrides | None,
) -> CleanDesignTreeNode:
    if overrides is None:
        return node
    updates: dict[str, object] = {}
    style_updates: dict[str, object] = {}
    if overrides.text is not None:
        if overrides.text != node.text:
            _record_override_mutation(
                node_id=node.id,
                field="text",
                old=node.text,
                new=overrides.text,
            )
        updates["text"] = overrides.text
    if overrides.accessibility_label is not None:
        if overrides.accessibility_label != node.accessibility_label:
            _record_override_mutation(
                node_id=node.id,
                field="accessibility_label",
                old=node.accessibility_label,
                new=overrides.accessibility_label,
            )
        updates["accessibility_label"] = overrides.accessibility_label
    if overrides.text_color is not None:
        if overrides.text_color != node.style.text_color:
            _record_override_mutation(
                node_id=node.id,
                field="style.text_color",
                old=node.style.text_color,
                new=overrides.text_color,
            )
        style_updates["text_color"] = overrides.text_color
    if overrides.background_color is not None:
        if overrides.background_color != node.style.background_color:
            _record_override_mutation(
                node_id=node.id,
                field="style.background_color",
                old=node.style.background_color,
                new=overrides.background_color,
            )
        style_updates["background_color"] = overrides.background_color
    if overrides.font_size is not None:
        if overrides.font_size != node.style.font_size:
            _record_override_mutation(
                node_id=node.id,
                field="style.font_size",
                old=node.style.font_size,
                new=overrides.font_size,
            )
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
    clean_index: dict[str, CleanDesignTreeNode] | None = None,
) -> CleanDesignTreeNode:
    """Apply IR child ordering/filtering onto a clean-tree node."""
    merged = _apply_ir_overrides(clean, ir.overrides)
    if clean.id in omit_ids:
        return merged.model_copy(update={"children": []})
    if ir.kind == WidgetIrKind.EXTRACTED:
        from figma_flutter_agent.parser.interaction import must_inline_extracted_widget_host

        if must_inline_extracted_widget_host(merged):
            return merged
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
        if clean.component_ref is not None and clean.children:
            preserved = [child for child in clean.children if child.id not in omit_ids]
            return merged.model_copy(update={"children": preserved})
        return merged
    clean_child_by_id = {child.id: child for child in clean.children}
    merged_children: list[CleanDesignTreeNode] = []
    emitted_ids: set[str] = set()
    for ir_child in ir.children:
        clean_child = clean_child_by_id.get(ir_child.figma_id)
        if clean_child is None and clean_index is not None:
            from figma_flutter_agent.generator.ir.passes.sectionize import (
                materialize_band_clean_node,
            )

            clean_child = materialize_band_clean_node(ir_child, clean_index)
        if clean_child is None or clean_child.id in omit_ids:
            continue
        emitted_ids.add(clean_child.id)
        merged_children.append(
            merge_ir_node(
                clean_child,
                ir_child,
                omit_ids=omit_ids,
                extracted_class_by_widget_name=extracted_class_by_widget_name,
                clean_index=clean_index,
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


def resolve_stack_child_order(
    clean: list[str],
    partial: list[str],
) -> tuple[list[str], list[str]]:
    """Resolve STACK paint order with clean-tree authority (E0.3).

    Nodes present in *clean* keep Figma paint order from *clean*.
    IR-only ids (in *partial* but not *clean*) are inserted at their declared
    positions from *partial*. Shared-node reordering in *partial* is ignored.

    Args:
        clean: Canonical child id order from the clean design tree.
        partial: LLM-provided ``stackChildOrder`` list.

    Returns:
        Tuple of resolved paint order and shared node ids whose LLM order differed.
    """
    clean_set = set(clean)
    partial_set = set(partial)
    partial_index = {node_id: index for index, node_id in enumerate(partial)}

    shared_in_partial = [node_id for node_id in partial if node_id in clean_set]
    shared_in_clean_order = [node_id for node_id in clean if node_id in partial_set]
    discrepancies: list[str] = []
    if shared_in_partial != shared_in_clean_order:
        discrepancies = list(dict.fromkeys(shared_in_partial))

    result = list(clean)
    ir_only = [node_id for node_id in partial if node_id not in clean_set]
    for ir_id in ir_only:
        ir_pos = partial_index[ir_id]
        insert_at = len(result)
        for index, existing in enumerate(result):
            existing_pos = partial_index.get(existing)
            if existing_pos is not None and existing_pos > ir_pos:
                insert_at = index
                break
        result.insert(insert_at, ir_id)

    return result, discrepancies


def merge_partial_stack_child_order(
    clean: list[str],
    partial: list[str],
) -> list[str]:
    """Return resolved STACK child order (clean-tree authoritative)."""
    order, _ = resolve_stack_child_order(clean, partial)
    return order


def merge_screen_ir(
    root: CleanDesignTreeNode,
    screen_ir: ScreenIr,
    *,
    extracted_class_by_widget_name: dict[str, str] | None = None,
) -> CleanDesignTreeNode:
    """Return a clean tree with ``screen_ir`` structure applied at ``root``."""
    omit_ids = frozenset(screen_ir.omit_figma_ids)
    clean_index = index_clean_tree(root)
    merged = merge_ir_node(
        root,
        screen_ir.root,
        omit_ids=omit_ids,
        extracted_class_by_widget_name=extracted_class_by_widget_name,
        clean_index=clean_index,
    )
    if screen_ir.stack_child_order and merged.type.value == "STACK":
        by_id = {child.id: child for child in merged.children}
        clean_order = [child.id for child in root.children if child.id in by_id]
        merged_order, discrepancies = resolve_stack_child_order(
            clean_order,
            screen_ir.stack_child_order,
        )
        if discrepancies:
            logger.warning(
                "Ignoring LLM stackChildOrder reorder for {} shared node(s): {}",
                len(discrepancies),
                ", ".join(discrepancies),
            )
        reordered = [by_id[node_id] for node_id in merged_order if node_id in by_id]
        merged = merged.model_copy(update={"children": reordered})
    return merged

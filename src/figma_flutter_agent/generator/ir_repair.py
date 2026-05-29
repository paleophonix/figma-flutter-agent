"""Apply structured screen IR patches from analyze/visual repair loops."""

from __future__ import annotations

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.schemas import (
    ScreenIr,
    WidgetIrNode,
    WidgetIrOverrides,
)


def _find_parent_and_index(
    root: WidgetIrNode,
    figma_id: str,
) -> tuple[WidgetIrNode | None, int | None]:
    if root.figma_id == figma_id:
        return None, None
    for index, child in enumerate(root.children):
        if child.figma_id == figma_id:
            return root, index
        parent, child_index = _find_parent_and_index(child, figma_id)
        if parent is not None or child_index is not None:
            return parent, child_index
    return None, None


def _find_node(root: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if root.figma_id == figma_id:
        return root
    for child in root.children:
        found = _find_node(child, figma_id)
        if found is not None:
            return found
    return None


def _merge_overrides(
    node: WidgetIrNode,
    overrides: WidgetIrOverrides | None,
) -> WidgetIrNode:
    if overrides is None:
        return node
    merged = node.model_copy(deep=True)
    existing = merged.overrides.model_copy(deep=True) if merged.overrides else WidgetIrOverrides()
    if overrides.text is not None:
        existing = existing.model_copy(update={"text": overrides.text})
    if overrides.accessibility_label is not None:
        existing = existing.model_copy(
            update={"accessibility_label": overrides.accessibility_label},
        )
    return merged.model_copy(update={"overrides": existing})


def apply_ir_patch_to_screen(
    screen_ir: ScreenIr,
    *,
    figma_id: str,
    replace_subtree: WidgetIrNode | None = None,
    overrides: WidgetIrOverrides | None = None,
    reorder_children: list[str] | None = None,
) -> ScreenIr:
    """Return an updated ``ScreenIr`` after one patch operation."""
    if screen_ir.root.figma_id == figma_id and replace_subtree is not None:
        return screen_ir.model_copy(update={"root": replace_subtree})

    parent, index = _find_parent_and_index(screen_ir.root, figma_id)
    node = _find_node(screen_ir.root, figma_id)
    if node is None:
        raise GenerationError(f"ir patch figmaId {figma_id!r} not found in screenIr")

    if replace_subtree is not None:
        if parent is None or index is None:
            return screen_ir.model_copy(update={"root": replace_subtree})
        new_children = list(parent.children)
        new_children[index] = replace_subtree
        updated_parent = parent.model_copy(update={"children": new_children})
        return _replace_node_in_root(screen_ir, updated_parent)

    updated_node = node
    if overrides is not None:
        updated_node = _merge_overrides(updated_node, overrides)
    if reorder_children is not None:
        by_id = {child.figma_id: child for child in updated_node.children}
        ordered = [by_id[cid] for cid in reorder_children if cid in by_id]
        tail = [child for child in updated_node.children if child.figma_id not in reorder_children]
        updated_node = updated_node.model_copy(update={"children": [*ordered, *tail]})

    if parent is None or index is None:
        return screen_ir.model_copy(update={"root": updated_node})
    new_children = list(parent.children)
    new_children[index] = updated_node
    updated_parent = parent.model_copy(update={"children": new_children})
    return _replace_node_in_root(screen_ir, updated_parent)


def _replace_node_in_root(screen_ir: ScreenIr, updated: WidgetIrNode) -> ScreenIr:
    if screen_ir.root.figma_id == updated.figma_id:
        return screen_ir.model_copy(update={"root": updated})
    new_root = _replace_descendant(screen_ir.root, updated)
    return screen_ir.model_copy(update={"root": new_root})


def _replace_descendant(root: WidgetIrNode, updated: WidgetIrNode) -> WidgetIrNode:
    if root.figma_id == updated.figma_id:
        return updated
    children = [_replace_descendant(child, updated) for child in root.children]
    return root.model_copy(update={"children": children})

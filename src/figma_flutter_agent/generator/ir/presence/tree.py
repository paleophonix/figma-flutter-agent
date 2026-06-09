"""IR and clean-tree traversal helpers for presence normalization."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, WidgetIrKind, WidgetIrNode


def ir_figma_ids(root: WidgetIrNode) -> set[str]:
    ids: set[str] = set()

    def walk(node: WidgetIrNode) -> None:
        ids.add(node.figma_id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def clean_parent(
    node_id: str,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> CleanDesignTreeNode | None:
    for candidate in tree_by_id.values():
        if any(child.id == node_id for child in candidate.children):
            return candidate
    return None


def find_ir_node(root: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if root.figma_id == figma_id:
        return root
    for child in root.children:
        found = find_ir_node(child, figma_id)
        if found is not None:
            return found
    return None


def build_clean_parent_map(
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> dict[str, str]:
    parent_by_id: dict[str, str] = {}
    for parent_id, parent in tree_by_id.items():
        for child in parent.children:
            parent_by_id[child.id] = parent_id
    return parent_by_id


def extracted_ir_nodes(root: WidgetIrNode) -> list[WidgetIrNode]:
    found: list[WidgetIrNode] = []

    def walk(node: WidgetIrNode) -> None:
        if node.kind == WidgetIrKind.EXTRACTED:
            found.append(node)
        for child in node.children:
            walk(child)

    walk(root)
    return found


def is_clean_descendant_of(
    node_id: str,
    ancestor_id: str,
    *,
    parent_by_id: dict[str, str],
) -> bool:
    current = node_id
    while current in parent_by_id:
        current = parent_by_id[current]
        if current == ancestor_id:
            return True
    return False


def ir_subtree_contains_figma_id(root: WidgetIrNode, figma_id: str) -> bool:
    if root.figma_id == figma_id:
        return True
    return any(ir_subtree_contains_figma_id(child, figma_id) for child in root.children)


def ir_node_by_figma_id(root: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    return find_ir_node(root, figma_id)


def extracted_reference_valid(
    ir_node: WidgetIrNode,
    extracted_widget_names: frozenset[str] | None,
) -> bool:
    if ir_node.kind != WidgetIrKind.EXTRACTED:
        return True
    ref_name = (ir_node.ref.widget_name if ir_node.ref else "").strip()
    if not ref_name:
        return False
    if extracted_widget_names is None:
        return True
    return ref_name in extracted_widget_names

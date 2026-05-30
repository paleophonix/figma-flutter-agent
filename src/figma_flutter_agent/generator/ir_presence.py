"""Ensure large deterministic subtrees appear in screen IR before emission."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir_tree import index_clean_tree
from figma_flutter_agent.generator.ir_validate import stack_placement_bounded_for_ir
from figma_flutter_agent.generator.subtree_widgets import (
    SubtreeWidgetSpec,
    _should_insert_missing_subtree,
    collect_subtree_widget_specs,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)

_STACK_VISUAL_NODE_TYPES = frozenset(
    {
        NodeType.VECTOR,
        NodeType.IMAGE,
        NodeType.CONTAINER,
    }
)
_MIN_STACK_VISUAL_IR_COVERAGE = 0.95


def _ir_figma_ids(root: WidgetIrNode) -> set[str]:
    ids: set[str] = set()

    def walk(node: WidgetIrNode) -> None:
        ids.add(node.figma_id)
        for child in node.children:
            walk(child)

    walk(root)
    return ids


def _attach_presence_child(
    screen_ir: ScreenIr,
    *,
    spec: SubtreeWidgetSpec,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    """Insert an AUTO IR node for a clean-tree subtree omitted by the LLM."""
    clean = tree_by_id.get(spec.node_id)
    if clean is None:
        return False
    parent_id = _screen_stack_parent_id(spec.node_id, screen_ir=screen_ir, tree_by_id=tree_by_id)
    if parent_id is None:
        return False
    parent_ir = _find_ir_node(screen_ir.root, parent_id)
    if parent_ir is None:
        return False
    if any(child.figma_id == spec.node_id for child in parent_ir.children):
        return True
    parent_ir.children.append(
        WidgetIrNode(
            figma_id=spec.node_id,
            kind=WidgetIrKind.AUTO,
            children=[],
        )
    )
    logger.info(
        "Inserted presence IR node for {} (figmaId={}) under parent {}",
        spec.class_name,
        spec.node_id,
        parent_id,
    )
    return True


def _screen_stack_parent_id(
    node_id: str,
    *,
    screen_ir: ScreenIr,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> str | None:
    """Return the IR parent id that should list ``node_id`` as a direct stack child."""
    node = tree_by_id.get(node_id)
    if node is None:
        return None
    current_id = node_id
    while True:
        parent = _clean_parent(current_id, tree_by_id)
        if parent is None:
            return screen_ir.root.figma_id
        if parent.id == screen_ir.root.figma_id:
            return screen_ir.root.figma_id
        if parent.stack_placement is not None:
            return parent.id
        current_id = parent.id


def _clean_parent(
    node_id: str,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> CleanDesignTreeNode | None:
    for candidate in tree_by_id.values():
        if any(child.id == node_id for child in candidate.children):
            return candidate
    return None


def _find_ir_node(root: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if root.figma_id == figma_id:
        return root
    for child in root.children:
        found = _find_ir_node(child, figma_id)
        if found is not None:
            return found
    return None


def _build_clean_parent_map(
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> dict[str, str]:
    parent_by_id: dict[str, str] = {}
    for parent_id, parent in tree_by_id.items():
        for child in parent.children:
            parent_by_id[child.id] = parent_id
    return parent_by_id


def _extracted_ir_root_ids(root: WidgetIrNode) -> frozenset[str]:
    extracted: set[str] = set()

    def walk(node: WidgetIrNode) -> None:
        if node.kind == WidgetIrKind.EXTRACTED:
            extracted.add(node.figma_id)
        for child in node.children:
            walk(child)

    walk(root)
    return frozenset(extracted)


def _is_clean_descendant_of(
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


def _ir_subtree_contains_figma_id(root: WidgetIrNode, figma_id: str) -> bool:
    if root.figma_id == figma_id:
        return True
    return any(_ir_subtree_contains_figma_id(child, figma_id) for child in root.children)


def _extracted_ir_nodes(root: WidgetIrNode) -> list[WidgetIrNode]:
    found: list[WidgetIrNode] = []

    def walk(node: WidgetIrNode) -> None:
        if node.kind == WidgetIrKind.EXTRACTED:
            found.append(node)
        for child in node.children:
            walk(child)

    walk(root)
    return found


def _extracted_reference_valid(
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


def _stack_visual_covered_by_extracted_ir(
    screen_ir: ScreenIr,
    node_id: str,
    *,
    parent_by_id: dict[str, str],
    extracted_widget_names: frozenset[str] | None,
) -> bool:
    for extracted_ir in _extracted_ir_nodes(screen_ir.root):
        if not _extracted_reference_valid(extracted_ir, extracted_widget_names):
            continue
        if not _is_clean_descendant_of(
            node_id,
            extracted_ir.figma_id,
            parent_by_id=parent_by_id,
        ):
            continue
        if _ir_subtree_contains_figma_id(extracted_ir, node_id):
            return True
    return False


def _container_requires_stack_visual_ir(node: CleanDesignTreeNode) -> bool:
    if node.type != NodeType.CONTAINER:
        return False
    if node.style.background_color or node.children:
        return True
    if node.style.border_width is not None and node.style.border_width > 0:
        return True
    if node.style.border_color:
        return True
    placement = node.stack_placement
    return placement is not None and (
        (placement.width or 0) > 0 or (placement.height or 0) > 0
    )


def _ensure_ir_stack_parent(
    screen_ir: ScreenIr,
    *,
    parent_id: str,
    tree_by_id: dict[str, CleanDesignTreeNode],
    present: set[str],
) -> bool:
    if parent_id == screen_ir.root.figma_id:
        return True
    if parent_id in present or _find_ir_node(screen_ir.root, parent_id) is not None:
        present.add(parent_id)
        return True
    clean = tree_by_id.get(parent_id)
    if clean is None:
        return False
    grandparent_id = _screen_stack_parent_id(
        parent_id,
        screen_ir=screen_ir,
        tree_by_id=tree_by_id,
    )
    if grandparent_id is None:
        return False
    if not _ensure_ir_stack_parent(
        screen_ir,
        parent_id=grandparent_id,
        tree_by_id=tree_by_id,
        present=present,
    ):
        return False
    grandparent_ir = _find_ir_node(screen_ir.root, grandparent_id)
    if grandparent_ir is None:
        return False
    if any(child.figma_id == parent_id for child in grandparent_ir.children):
        present.add(parent_id)
        return True
    kind = WidgetIrKind.STACK if clean.type == NodeType.STACK else WidgetIrKind.AUTO
    grandparent_ir.children.append(
        WidgetIrNode(
            figma_id=parent_id,
            kind=kind,
            children=[],
        )
    )
    present.add(parent_id)
    logger.info(
        "Inserted stack-parent IR node for figmaId={} under {}",
        parent_id,
        grandparent_id,
    )
    return True


def _ir_kind_for_clean_node(clean: CleanDesignTreeNode) -> WidgetIrKind:
    if clean.type == NodeType.STACK:
        return WidgetIrKind.STACK
    if clean.type == NodeType.COLUMN:
        return WidgetIrKind.COLUMN
    if clean.type == NodeType.ROW:
        return WidgetIrKind.ROW
    if clean.type == NodeType.TEXT:
        return WidgetIrKind.TEXT
    if clean.type == NodeType.BUTTON:
        return WidgetIrKind.BUTTON
    if clean.type == NodeType.INPUT:
        return WidgetIrKind.INPUT
    if clean.type == NodeType.CONTAINER:
        return WidgetIrKind.CONTAINER
    if clean.type == NodeType.IMAGE:
        return WidgetIrKind.IMAGE
    return WidgetIrKind.AUTO


def _should_downgrade_extracted_stack(
    ir_node: WidgetIrNode,
    clean: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None,
) -> bool:
    if clean.type != NodeType.STACK or ir_node.kind != WidgetIrKind.EXTRACTED:
        return False
    if _extracted_reference_valid(ir_node, extracted_widget_names):
        return False
    return any(
        child.stack_placement is not None and child.type in _STACK_VISUAL_NODE_TYPES
        for child in clean.children
    )


def sync_screen_ir_stack_subtree_from_clean_tree(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None = None,
) -> ScreenIr:
    """Mirror clean-tree STACK children into screen IR so stack-placed nodes are not dropped."""
    screen_ir = screen_ir.model_copy(deep=True)
    tree_by_id = index_clean_tree(clean_tree)
    omit = frozenset(screen_ir.omit_figma_ids)
    root_ir = _find_ir_node(screen_ir.root, screen_ir.root.figma_id)
    root_clean = tree_by_id.get(screen_ir.root.figma_id)
    if root_ir is None or root_clean is None or root_clean.type != NodeType.STACK:
        return screen_ir

    def merge_child(
        clean_child: CleanDesignTreeNode,
        existing: WidgetIrNode | None,
    ) -> WidgetIrNode:
        if existing is not None and existing.kind == WidgetIrKind.EXTRACTED:
            if not _should_downgrade_extracted_stack(
                existing,
                clean_child,
                extracted_widget_names=extracted_widget_names,
            ):
                return existing
            existing = existing.model_copy(
                update={"kind": _ir_kind_for_clean_node(clean_child), "ref": None},
            )
        if existing is not None:
            ir_child = existing.model_copy(deep=True)
            if ir_child.kind == WidgetIrKind.EXTRACTED:
                return ir_child
        else:
            ir_child = WidgetIrNode(
                figma_id=clean_child.id,
                kind=_ir_kind_for_clean_node(clean_child),
                children=[],
            )
        if clean_child.type == NodeType.STACK:
            sync_stack_children(ir_child, clean_child)
        return ir_child

    def sync_stack_children(ir_node: WidgetIrNode, clean: CleanDesignTreeNode) -> None:
        if clean.type != NodeType.STACK:
            return
        if ir_node.kind == WidgetIrKind.EXTRACTED and _extracted_reference_valid(
            ir_node,
            extracted_widget_names,
        ):
            return
        existing_by_id = {child.figma_id: child for child in ir_node.children}
        merged: list[WidgetIrNode] = []
        for clean_child in clean.children:
            if clean_child.id in omit:
                continue
            merged.append(
                merge_child(clean_child, existing_by_id.get(clean_child.id)),
            )
        ir_node.children = merged

    sync_stack_children(root_ir, root_clean)
    return screen_ir


def normalize_screen_ir_presence(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    widget_suffix: str = "Widget",
    extracted_widget_names: frozenset[str] | None = None,
) -> ScreenIr:
    """Deterministically fill large subtrees and stack-placed visuals omitted by the LLM."""
    screen_ir = ensure_presence_subtrees_in_screen_ir(
        screen_ir,
        clean_tree,
        widget_suffix=widget_suffix,
    )
    screen_ir = ensure_stack_visual_nodes_in_screen_ir(
        screen_ir,
        clean_tree,
        extracted_widget_names=extracted_widget_names,
    )
    return sync_screen_ir_stack_subtree_from_clean_tree(
        screen_ir,
        clean_tree,
        extracted_widget_names=extracted_widget_names,
    )


def ensure_presence_subtrees_in_screen_ir(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    widget_suffix: str = "Widget",
) -> ScreenIr:
    """Add AUTO IR nodes for large subtree widgets missing from the LLM screen graph."""
    specs = collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix)
    if not specs:
        return screen_ir
    screen_ir = screen_ir.model_copy(deep=True)
    tree_by_id = index_clean_tree(clean_tree)
    present = _ir_figma_ids(screen_ir.root)
    for spec in specs:
        if not _should_insert_missing_subtree(spec):
            continue
        if spec.node_id in present:
            continue
        if _attach_presence_child(screen_ir, spec=spec, tree_by_id=tree_by_id):
            present.add(spec.node_id)
    return screen_ir


def _ir_node_by_figma_id(root: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if root.figma_id == figma_id:
        return root
    for child in root.children:
        found = _ir_node_by_figma_id(child, figma_id)
        if found is not None:
            return found
    return None


def _stack_visual_node_requires_ir(
    node: CleanDesignTreeNode,
    *,
    screen_ir: ScreenIr,
    node_id: str,
    parent_by_id: dict[str, str],
    extracted_widget_names: frozenset[str] | None,
) -> bool:
    if node.stack_placement is None or node.type not in _STACK_VISUAL_NODE_TYPES:
        return False
    if not stack_placement_bounded_for_ir(node):
        return False
    if _stack_visual_covered_by_extracted_ir(
        screen_ir,
        node_id,
        parent_by_id=parent_by_id,
        extracted_widget_names=extracted_widget_names,
    ):
        return False
    if node.type == NodeType.CONTAINER:
        return _container_requires_stack_visual_ir(node)
    return True


def _attach_stack_visual_ir_node(
    screen_ir: ScreenIr,
    *,
    node_id: str,
    tree_by_id: dict[str, CleanDesignTreeNode],
    present: set[str],
) -> bool:
    clean = tree_by_id.get(node_id)
    if clean is None:
        return False
    parent_id = _screen_stack_parent_id(node_id, screen_ir=screen_ir, tree_by_id=tree_by_id)
    if parent_id is None:
        return False
    if not _ensure_ir_stack_parent(
        screen_ir,
        parent_id=parent_id,
        tree_by_id=tree_by_id,
        present=present,
    ):
        return False
    parent_ir = _find_ir_node(screen_ir.root, parent_id)
    if parent_ir is None:
        return False
    if parent_ir.kind == WidgetIrKind.EXTRACTED:
        return False
    if any(child.figma_id == node_id for child in parent_ir.children):
        return True
    parent_ir.children.append(
        WidgetIrNode(
            figma_id=node_id,
            kind=WidgetIrKind.AUTO,
            children=[],
        )
    )
    logger.info(
        "Inserted stack-visual IR node for figmaId={} under parent {}",
        node_id,
        parent_id,
    )
    return True


def ensure_stack_visual_nodes_in_screen_ir(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None = None,
) -> ScreenIr:
    """Insert AUTO IR nodes for stack-placed vectors/images/containers omitted by the LLM."""
    screen_ir = screen_ir.model_copy(deep=True)
    tree_by_id = index_clean_tree(clean_tree)
    parent_by_id = _build_clean_parent_map(tree_by_id)
    present = _ir_figma_ids(screen_ir.root)
    omit = frozenset(screen_ir.omit_figma_ids)
    for node_id, node in tree_by_id.items():
        if node_id in omit or node_id in present:
            continue
        if not _stack_visual_node_requires_ir(
            node,
            screen_ir=screen_ir,
            node_id=node_id,
            parent_by_id=parent_by_id,
            extracted_widget_names=extracted_widget_names,
        ):
            continue
        if _attach_stack_visual_ir_node(
            screen_ir,
            node_id=node_id,
            tree_by_id=tree_by_id,
            present=present,
        ):
            present.add(node_id)
    return screen_ir


def validate_stack_visual_ir_coverage(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None = None,
    min_coverage: float = _MIN_STACK_VISUAL_IR_COVERAGE,
) -> None:
    """Raise when stack-placed visual IR coverage falls below ``min_coverage``."""
    screen_ir = normalize_screen_ir_presence(
        screen_ir,
        clean_tree,
        extracted_widget_names=extracted_widget_names,
    )
    tree_by_id = index_clean_tree(clean_tree)
    parent_by_id = _build_clean_parent_map(tree_by_id)
    omit = frozenset(screen_ir.omit_figma_ids)
    required = 0
    present = 0
    missing: list[str] = []
    for node_id, node in tree_by_id.items():
        if node_id in omit:
            continue
        if not _stack_visual_node_requires_ir(
            node,
            screen_ir=screen_ir,
            node_id=node_id,
            parent_by_id=parent_by_id,
            extracted_widget_names=extracted_widget_names,
        ):
            continue
        required += 1
        if _ir_node_by_figma_id(screen_ir.root, node_id) is None:
            missing.append(node_id)
        else:
            present += 1
    if required == 0:
        return
    ratio = present / required
    if ratio < min_coverage:
        sample = ", ".join(missing[:8])
        raise GenerationError(
            "screenIr stack-placed visual coverage "
            f"{ratio:.1%} below {min_coverage:.0%} threshold "
            f"({present}/{required} present; missing: {sample})"
        )

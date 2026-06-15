"""IR graph integrity checks and clean-tree alignment."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.tree import index_clean_tree
from figma_flutter_agent.generator.layout.widgets import figma_positioned_dimensions
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
)


def _walk_ir(node: WidgetIrNode) -> list[WidgetIrNode]:
    nodes = [node]
    for child in node.children:
        nodes.extend(_walk_ir(child))
    return nodes


def _validate_ir_graph_integrity(root: WidgetIrNode) -> None:
    visited_ids: set[str] = set()

    def walk(node: WidgetIrNode, ancestor_ids: frozenset[str]) -> None:
        if node.figma_id in ancestor_ids:
            raise GenerationError(
                f"screenIr contains a cycle at figmaId {node.figma_id!r} "
                "(node cannot be its own descendant)"
            )
        if node.figma_id in visited_ids:
            raise GenerationError(
                f"screenIr figmaId {node.figma_id!r} appears more than once; "
                "each Figma id must map to exactly one widget"
            )
        visited_ids.add(node.figma_id)
        for child in node.children:
            walk(child, ancestor_ids | {node.figma_id})

    walk(root, frozenset())


def _build_parent_map(root: CleanDesignTreeNode) -> dict[str, str]:
    parents: dict[str, str] = {}

    def walk(node: CleanDesignTreeNode, parent_id: str | None) -> None:
        if parent_id is not None:
            parents[node.id] = parent_id
        for child in node.children:
            walk(child, node.id)

    walk(root, None)
    return parents


def _viewport_size(root: CleanDesignTreeNode) -> tuple[float, float] | None:
    width = root.sizing.width
    height = root.sizing.height
    if width is None or height is None or width <= 0 or height <= 0:
        return None
    return width, height


def _has_stack_ancestor(
    node_id: str,
    *,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    current = parent_by_id.get(node_id)
    while current is not None:
        ancestor = tree_by_id.get(current)
        if ancestor is None:
            return False
        if ancestor.type == NodeType.STACK:
            return True
        current = parent_by_id.get(current)
    return False


def _stack_has_bounded_horizontal(placement: StackPlacement, clean: CleanDesignTreeNode) -> bool:
    width, _ = figma_positioned_dimensions(clean, placement)
    if width is not None:
        return True
    if placement.horizontal in {"LEFT_RIGHT", "SCALE"}:
        return True
    return (
        placement.left is not None
        and placement.right is not None
        and ((placement.left or 0.0) > 0.0 or (placement.right or 0.0) > 0.0)
    )


def _stack_has_bounded_vertical(placement: StackPlacement, clean: CleanDesignTreeNode) -> bool:
    width, height = figma_positioned_dimensions(clean, placement)
    if height is not None:
        return True
    if placement.vertical in {"TOP_BOTTOM", "SCALE"}:
        return True
    if (
        placement.top is not None
        and placement.bottom is not None
        and placement.bottom >= 0
    ):
        return True
    if clean.style.has_stroke and (width or 0) > 0:
        stroke = clean.style.border_width or 3.0
        if width >= stroke * 4:
            return True
    return False


def stack_placement_bounded_for_ir(clean: CleanDesignTreeNode) -> bool:
    """Return whether stack placement can be emitted without unbounded Positioned axes."""
    placement = clean.stack_placement
    if placement is None:
        return True
    return _stack_has_bounded_horizontal(placement, clean) and _stack_has_bounded_vertical(
        placement,
        clean,
    )


def _validate_stack_placement_bounds(clean: CleanDesignTreeNode) -> None:
    placement = clean.stack_placement
    if placement is None:
        return
    if not _stack_has_bounded_horizontal(placement, clean):
        raise GenerationError(
            f"IR node {clean.id!r} has stackPlacement without bounded width "
            "(set placement.width, sizing.width, or horizontal LEFT_RIGHT/SCALE); "
            "unbounded Stack/Positioned will crash at runtime"
        )
    if not _stack_has_bounded_vertical(placement, clean):
        raise GenerationError(
            f"IR node {clean.id!r} has stackPlacement without bounded height "
            "(set placement.height, sizing.height, or vertical TOP_BOTTOM/SCALE); "
            "unbounded Stack/Positioned will crash at runtime"
        )


def _index_ir_nodes(root: WidgetIrNode) -> dict[str, WidgetIrNode]:
    return {node.figma_id: node for node in _walk_ir(root)}


def _attach_ir_child_unique(ir_parent: WidgetIrNode, ir_child: WidgetIrNode) -> bool:
    if any(existing.figma_id == ir_child.figma_id for existing in ir_parent.children):
        return False
    ir_parent.children.append(ir_child)
    return True


def _downgrade_extracted_host_if_blocking(
    host: WidgetIrNode,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> WidgetIrNode | None:
    if host.kind != WidgetIrKind.EXTRACTED:
        return host
    clean = tree_by_id.get(host.figma_id)
    if clean is None:
        return None
    logger.warning(
        "Downgraded extracted IR host {} blocking child realignment",
        host.figma_id,
    )
    host.kind = _ir_kind_for_clean_stub(clean)
    host.ref = None
    return host


def _resolve_ir_host_for_clean_child(
    child_figma_id: str,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
    parent_by_id: dict[str, str],
    ir_by_id: dict[str, WidgetIrNode],
) -> WidgetIrNode | None:
    clean_parent_id = parent_by_id.get(child_figma_id)
    if clean_parent_id is None:
        return None
    host = ir_by_id.get(clean_parent_id)
    if host is None:
        return None
    if host.kind == WidgetIrKind.EXTRACTED:
        return _downgrade_extracted_host_if_blocking(host, tree_by_id=tree_by_id)
    return host


def _ir_kind_for_clean_stub(clean: CleanDesignTreeNode) -> WidgetIrKind:
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


def _ensure_ir_hosts_on_path(
    clean_parent_id: str,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
    parent_by_id: dict[str, str],
    ir_by_id: dict[str, WidgetIrNode],
) -> WidgetIrNode | None:
    missing_chain: list[str] = []
    walk = clean_parent_id
    while walk and walk not in ir_by_id:
        missing_chain.append(walk)
        walk = parent_by_id.get(walk)
    anchor_id = walk
    if anchor_id is None or anchor_id not in ir_by_id:
        return None
    host = ir_by_id[anchor_id]
    for node_id in reversed(missing_chain):
        clean = tree_by_id.get(node_id)
        if clean is None:
            return None
        stub = WidgetIrNode(
            figma_id=node_id,
            kind=_ir_kind_for_clean_stub(clean),
            children=[],
        )
        if not _attach_ir_child_unique(host, stub):
            host = ir_by_id[node_id]
        else:
            ir_by_id[node_id] = stub
            host = stub
    if host.kind == WidgetIrKind.EXTRACTED:
        return _downgrade_extracted_host_if_blocking(host, tree_by_id=tree_by_id)
    return host


def _realign_ir_node_children_to_clean_tree(
    ir_node: WidgetIrNode,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
    parent_by_id: dict[str, str],
    ir_by_id: dict[str, WidgetIrNode],
) -> int:
    clean = tree_by_id.get(ir_node.figma_id)
    if clean is None:
        return 0
    direct_ids = {child.id for child in clean.children}
    kept: list[WidgetIrNode] = []
    misplaced: list[WidgetIrNode] = []
    for ir_child in ir_node.children:
        if ir_child.figma_id in direct_ids:
            kept.append(ir_child)
        else:
            misplaced.append(ir_child)
    ir_node.children = kept
    moved = 0
    for ir_child in misplaced:
        clean_parent_id = parent_by_id.get(ir_child.figma_id)
        if clean_parent_id is None:
            logger.warning(
                "Dropped screenIr child {}: not present in clean-tree parent map",
                ir_child.figma_id,
            )
            continue
        host = _resolve_ir_host_for_clean_child(
            ir_child.figma_id,
            tree_by_id=tree_by_id,
            parent_by_id=parent_by_id,
            ir_by_id=ir_by_id,
        )
        if host is None:
            host = _ensure_ir_hosts_on_path(
                clean_parent_id,
                tree_by_id=tree_by_id,
                parent_by_id=parent_by_id,
                ir_by_id=ir_by_id,
            )
        if host is None:
            logger.warning(
                "Dropped misplaced screenIr child {}: clean parent {} not representable in screenIr",
                ir_child.figma_id,
                clean_parent_id,
            )
            continue
        if _attach_ir_child_unique(host, ir_child):
            moved += 1
            logger.debug(
                "Realigned screenIr child {} under {} (was under {})",
                ir_child.figma_id,
                host.figma_id,
                ir_node.figma_id,
            )
    relocations = moved
    for child in list(ir_node.children):
        relocations += _realign_ir_node_children_to_clean_tree(
            child,
            tree_by_id=tree_by_id,
            parent_by_id=parent_by_id,
            ir_by_id=ir_by_id,
        )
    return relocations


_REALIGN_MAX_PASSES = 32


def realign_screen_ir_children_to_clean_tree(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
) -> int:
    """Reparent IR nodes in place so each child matches ``cleanTree`` direct-child links.

    Runs multiple passes because a subtree reparented onto an already-visited IR host
    still needs its descendants realigned in a later pass.

    Returns:
        Count of relocated child nodes across all passes.
    """
    tree_by_id = index_clean_tree(root)
    parent_by_id = _build_parent_map(root)
    total_moved = 0
    for _pass in range(_REALIGN_MAX_PASSES):
        ir_by_id = _index_ir_nodes(screen_ir.root)
        moved = _realign_ir_node_children_to_clean_tree(
            screen_ir.root,
            tree_by_id=tree_by_id,
            parent_by_id=parent_by_id,
            ir_by_id=ir_by_id,
        )
        total_moved += moved
        if moved == 0:
            break
    else:
        logger.warning(
            "screenIr child realignment stopped after {} passes with pending moves",
            _REALIGN_MAX_PASSES,
        )
    if total_moved:
        logger.info(
            "Realigned {} screenIr child node(s) to match cleanTree parent links",
            total_moved,
        )
    return total_moved


def ensure_ir_direct_children_match_clean(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
) -> int:
    """Mirror clean-tree direct-child links onto screen IR (stubs for missing nodes).

    LLM semantic nodes (e.g. ``kind=button``) often omit label/text children that
    remain in the clean tree. Dual-graph passes require identical child id sets.

    Args:
        screen_ir: Screen IR graph mutated in place.
        clean_tree: Authoritative clean design tree.

    Returns:
        Count of stub IR nodes inserted for missing clean children.
    """
    tree_by_id = index_clean_tree(clean_tree)
    omit = frozenset(screen_ir.omit_figma_ids or ())
    inserted = 0

    def walk(ir_node: WidgetIrNode) -> None:
        nonlocal inserted
        clean = tree_by_id.get(ir_node.figma_id)
        if clean is None:
            for child in ir_node.children:
                walk(child)
            return
        existing_by_id = {child.figma_id: child for child in ir_node.children}
        merged: list[WidgetIrNode] = []
        for clean_child in clean.children:
            if clean_child.id in omit:
                continue
            ir_child = existing_by_id.get(clean_child.id)
            if ir_child is None:
                ir_child = WidgetIrNode(
                    figma_id=clean_child.id,
                    kind=_ir_kind_for_clean_stub(clean_child),
                )
                inserted += 1
            merged.append(ir_child)
        ir_node.children = merged
        for child in merged:
            walk(child)

    walk(screen_ir.root)
    return inserted


def sync_screen_ir_graph_to_clean_tree(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
) -> int:
    """Realign IR parent links and stack child order to match ``clean_tree``.

    Call before dual-graph layout passes whenever the clean tree may have diverged
    from the cached IR snapshot (post-reconcile normalize, offline IR reload, etc.).

    Args:
        screen_ir: Screen IR graph mutated in place.
        clean_tree: Authoritative clean design tree for the same screen.

    Returns:
        Count of structural fixes (relocated children + inserted stubs).
    """
    moved = realign_screen_ir_children_to_clean_tree(screen_ir, clean_tree)
    inserted = ensure_ir_direct_children_match_clean(screen_ir, clean_tree)
    tree_by_id = index_clean_tree(clean_tree)
    _align_ir_stack_children_to_clean_tree(screen_ir.root, tree_by_id=tree_by_id)
    if inserted:
        logger.debug(
            "Inserted {} screenIr stub child node(s) to match clean-tree direct children",
            inserted,
        )
    return moved + inserted


def _ir_node_is_stack_host(ir_node: WidgetIrNode, clean: CleanDesignTreeNode) -> bool:
    if ir_node.kind == WidgetIrKind.STACK:
        return True
    return ir_node.kind == WidgetIrKind.AUTO and clean.type == NodeType.STACK


def _is_stack_interactive(clean: CleanDesignTreeNode, ir_node: WidgetIrNode) -> bool:
    _STACK_INTERACTIVE_TYPES = frozenset({NodeType.BUTTON, NodeType.INPUT})
    if ir_node.kind in {WidgetIrKind.BUTTON, WidgetIrKind.INPUT}:
        return True
    return clean.type in _STACK_INTERACTIVE_TYPES


def _is_opaque_stack_occluder(clean: CleanDesignTreeNode) -> bool:
    _STACK_OCCLUDER_TYPES = frozenset({NodeType.VECTOR, NodeType.IMAGE})
    if clean.type not in _STACK_OCCLUDER_TYPES:
        return False
    opacity = clean.style.opacity
    return not (opacity is not None and opacity < 0.05)


def _align_ir_stack_children_to_clean_tree(
    ir_node: WidgetIrNode,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> None:
    clean = tree_by_id.get(ir_node.figma_id)
    if clean is None:
        return
    if (
        _ir_node_is_stack_host(ir_node, clean)
        and ir_node.children
        and clean.children
        and all(child.stack_placement is not None for child in clean.children)
    ):
        clean_order = [child.id for child in clean.children]
        ir_by_id = {child.figma_id: child for child in ir_node.children}
        ordered = [ir_by_id[node_id] for node_id in clean_order if node_id in ir_by_id]
        seen = frozenset(clean_order)
        tail = [child for child in ir_node.children if child.figma_id not in seen]
        ir_node.children = [*ordered, *tail]
    for child in ir_node.children:
        _align_ir_stack_children_to_clean_tree(child, tree_by_id=tree_by_id)

"""Stack visual presence rules for screen IR."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.ir.presence.constants import (
    MAX_STACK_VISUAL_IR_INSERTS,
    STACK_VISUAL_NODE_TYPES,
)
from figma_flutter_agent.generator.ir.presence.kinds import ir_kind_for_clean_node
from figma_flutter_agent.generator.ir.presence.subtrees import (
    screen_stack_parent_id,
)
from figma_flutter_agent.generator.ir.presence.subtrees import (
    subtree_root_ids as collect_subtree_root_ids,
)
from figma_flutter_agent.generator.ir.presence.tree import (
    build_clean_parent_map,
    extracted_ir_nodes,
    extracted_reference_valid,
    find_ir_node,
    ir_figma_ids,
    ir_subtree_contains_figma_id,
    is_clean_descendant_of,
)
from figma_flutter_agent.generator.ir.tree import index_clean_tree
from figma_flutter_agent.generator.ir.validate import stack_placement_bounded_for_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
)


def stack_visual_covered_by_extracted_ir(
    screen_ir: ScreenIr,
    node_id: str,
    *,
    parent_by_id: dict[str, str],
    extracted_widget_names: frozenset[str] | None,
    subtree_root_ids: frozenset[str] | None = None,
) -> bool:
    for extracted_ir in extracted_ir_nodes(screen_ir.root):
        if not extracted_reference_valid(extracted_ir, extracted_widget_names):
            continue
        if not is_clean_descendant_of(node_id, extracted_ir.figma_id, parent_by_id=parent_by_id):
            continue
        if subtree_root_ids and extracted_ir.figma_id in subtree_root_ids:
            return True
        if ir_subtree_contains_figma_id(extracted_ir, node_id):
            return True
    return False


def layout_emitted_stack_decorative(node: CleanDesignTreeNode) -> bool:
    """Stroke-only chrome emitted from layout via vector SVG."""
    if node.type != NodeType.CONTAINER or not node.vector_asset_key:
        return False
    placement = node.stack_placement
    placement_height = (placement.height if placement is not None else None) or 0.0
    sizing_height = node.sizing.height or 0.0
    return sizing_height <= 1.0 and placement_height <= 1.0


def container_requires_stack_visual_ir(node: CleanDesignTreeNode) -> bool:
    if node.type != NodeType.CONTAINER:
        return False
    if node.render_boundary or layout_emitted_stack_decorative(node):
        return False
    if node.style.background_color or node.children:
        return True
    if node.style.border_width is not None and node.style.border_width > 0:
        return True
    if node.style.border_color:
        return True
    placement = node.stack_placement
    return placement is not None and ((placement.width or 0) > 0 or (placement.height or 0) > 0)


def should_downgrade_extracted_stack(
    ir_node: WidgetIrNode,
    clean: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None,
    subtree_root_ids: frozenset[str] | None = None,
) -> bool:
    if clean.type != NodeType.STACK or ir_node.kind != WidgetIrKind.EXTRACTED:
        return False
    has_stack_visual_children = any(
        child.stack_placement is not None and child.type in STACK_VISUAL_NODE_TYPES
        for child in clean.children
    )
    if not has_stack_visual_children:
        return False
    return not extracted_reference_valid(ir_node, extracted_widget_names)


def ensure_ir_stack_parent(
    screen_ir: ScreenIr,
    *,
    parent_id: str,
    tree_by_id: dict[str, CleanDesignTreeNode],
    present: set[str],
) -> bool:
    if parent_id == screen_ir.root.figma_id:
        return True
    if parent_id in present or find_ir_node(screen_ir.root, parent_id) is not None:
        present.add(parent_id)
        return True
    clean = tree_by_id.get(parent_id)
    if clean is None:
        return False
    grandparent_id = screen_stack_parent_id(parent_id, screen_ir=screen_ir, tree_by_id=tree_by_id)
    if grandparent_id is None:
        return False
    if not ensure_ir_stack_parent(
        screen_ir,
        parent_id=grandparent_id,
        tree_by_id=tree_by_id,
        present=present,
    ):
        return False
    grandparent_ir = find_ir_node(screen_ir.root, grandparent_id)
    if grandparent_ir is None:
        return False
    if any(child.figma_id == parent_id for child in grandparent_ir.children):
        present.add(parent_id)
        return True
    kind = WidgetIrKind.STACK if clean.type == NodeType.STACK else WidgetIrKind.AUTO
    grandparent_ir.children.append(WidgetIrNode(figma_id=parent_id, kind=kind))
    present.add(parent_id)
    logger.debug("Inserted stack-parent IR node for figmaId={} under {}", parent_id, grandparent_id)
    return True


def stack_visual_node_requires_ir(
    node: CleanDesignTreeNode,
    *,
    screen_ir: ScreenIr,
    node_id: str,
    parent_by_id: dict[str, str],
    extracted_widget_names: frozenset[str] | None,
    subtree_root_ids: frozenset[str] | None = None,
) -> bool:
    if node.stack_placement is None or node.type not in STACK_VISUAL_NODE_TYPES:
        return False
    if not stack_placement_bounded_for_ir(node):
        return False
    if stack_visual_covered_by_extracted_ir(
        screen_ir,
        node_id,
        parent_by_id=parent_by_id,
        extracted_widget_names=extracted_widget_names,
        subtree_root_ids=subtree_root_ids,
    ):
        return False
    if node.type == NodeType.CONTAINER:
        return container_requires_stack_visual_ir(node)
    return True


def attach_stack_visual_ir_node(
    screen_ir: ScreenIr,
    *,
    node_id: str,
    tree_by_id: dict[str, CleanDesignTreeNode],
    present: set[str],
    extracted_widget_names: frozenset[str] | None = None,
    subtree_root_ids: frozenset[str] | None = None,
) -> bool:
    clean = tree_by_id.get(node_id)
    if clean is None:
        return False
    parent_id = screen_stack_parent_id(node_id, screen_ir=screen_ir, tree_by_id=tree_by_id)
    if parent_id is None:
        return False
    if not ensure_ir_stack_parent(
        screen_ir, parent_id=parent_id, tree_by_id=tree_by_id, present=present
    ):
        return False
    parent_ir = find_ir_node(screen_ir.root, parent_id)
    if parent_ir is None:
        return False
    parent_clean = tree_by_id.get(parent_id)
    if parent_ir.kind == WidgetIrKind.EXTRACTED and parent_clean is not None:
        if should_downgrade_extracted_stack(
            parent_ir,
            parent_clean,
            extracted_widget_names=extracted_widget_names,
            subtree_root_ids=subtree_root_ids,
        ):
            parent_ir.kind = ir_kind_for_clean_node(parent_clean)
            parent_ir.ref = None
            parent_ir.children = []
        else:
            return False
    if any(child.figma_id == node_id for child in parent_ir.children):
        return True
    parent_ir.children.append(WidgetIrNode(figma_id=node_id, kind=WidgetIrKind.AUTO))
    logger.debug("Inserted stack-visual IR node for figmaId={} under parent {}", node_id, parent_id)
    return True


def ensure_stack_visual_nodes_in_screen_ir(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None = None,
    subtree_root_ids: frozenset[str] | None = None,
    widget_suffix: str = "Widget",
) -> ScreenIr:
    """Insert AUTO IR nodes for stack-placed vectors/images/containers omitted by the LLM."""
    screen_ir = screen_ir.model_copy(deep=True)
    if subtree_root_ids is None:
        subtree_root_ids = collect_subtree_root_ids(clean_tree, widget_suffix=widget_suffix)
    tree_by_id = index_clean_tree(clean_tree)
    parent_by_id = build_clean_parent_map(tree_by_id)
    present = ir_figma_ids(screen_ir.root)
    omit = frozenset(screen_ir.omit_figma_ids)
    inserted = 0
    skipped_cap = 0
    for node_id, node in tree_by_id.items():
        if inserted >= MAX_STACK_VISUAL_IR_INSERTS:
            skipped_cap += 1
            continue
        if node_id in omit or node_id in present:
            continue
        if not stack_visual_node_requires_ir(
            node,
            screen_ir=screen_ir,
            node_id=node_id,
            parent_by_id=parent_by_id,
            extracted_widget_names=extracted_widget_names,
            subtree_root_ids=subtree_root_ids,
        ):
            continue
        if attach_stack_visual_ir_node(
            screen_ir,
            node_id=node_id,
            tree_by_id=tree_by_id,
            present=present,
            extracted_widget_names=extracted_widget_names,
            subtree_root_ids=subtree_root_ids,
        ):
            present.add(node_id)
            inserted += 1
    if skipped_cap:
        logger.warning(
            "IR stack visual presence capped: inserted {}, skipped {} (max {})",
            inserted,
            skipped_cap,
            MAX_STACK_VISUAL_IR_INSERTS,
        )
    return screen_ir

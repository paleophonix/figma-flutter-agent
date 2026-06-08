"""Validate screen IR against a clean design tree before Dart emission."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.tree import default_screen_ir, index_clean_tree
from figma_flutter_agent.generator.layout.style import _normalize_hex_color
from figma_flutter_agent.generator.layout.widgets.render import figma_positioned_dimensions
from figma_flutter_agent.parser.accessibility import contrast_ratio, nearest_ancestor_fill_hex
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    FlexWrapIr,
    NodeType,
    ScreenIr,
    SizingMode,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrOverrides,
)

_WCAG_AA_MIN_RATIO = 4.5
_VIEWPORT_OVERFLOW_MARGIN_PX = 20.0
_MIN_TOUCH_TARGET_PX = 44.0
_INTERACTIVE_TOUCH_TYPES = frozenset(
    {
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.DROPDOWN,
    }
)
_ASSET_SUFFIXES = (".svg", ".png", ".webp", ".jpg", ".jpeg")
_KEYBOARD_BOTTOM_VIEWPORT_FRACTION = 0.5
_FONT_SIZE_SNAP_TOLERANCE = 0.75
_MAX_COLOR_SNAP_CHANNEL_DELTA = 24
_STACK_OCCLUDER_TYPES = frozenset({NodeType.VECTOR, NodeType.IMAGE})
_STACK_INTERACTIVE_TYPES = frozenset({NodeType.BUTTON, NodeType.INPUT})
_Bounds = tuple[float, float, float, float]


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
    return False


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


def _is_scroll_like_host(clean: CleanDesignTreeNode) -> bool:
    if clean.scroll_axis != "none":
        return True
    return clean.type == NodeType.GRID


def _flex_wrap_covers_parent_axis(
    ir_node: WidgetIrNode,
    *,
    parent_type: NodeType,
    clean: CleanDesignTreeNode,
) -> bool:
    wrap = ir_node.wrap
    if wrap == FlexWrapIr.EXPANDED:
        return True
    if parent_type == NodeType.COLUMN:
        if clean.sizing.height_mode == SizingMode.FIXED and (clean.sizing.height or 0) > 0:
            return True
        # Nested GridView/ListView hosts use shrinkWrap when not FILL-height flex children.
        if _is_scroll_like_host(clean) and clean.sizing.height_mode != SizingMode.FILL:
            return True
        return False
    if parent_type == NodeType.ROW:
        if wrap == FlexWrapIr.FLEXIBLE_LOOSE:
            return True
        if wrap == FlexWrapIr.SIZED_BOX_WIDTH:
            return True
        if clean.sizing.width_mode == SizingMode.FIXED and (clean.sizing.width or 0) > 0:
            return True
        return False
    return False


def _validate_flex_child_slot(
    ir_node: WidgetIrNode,
    clean: CleanDesignTreeNode,
    parent_clean: CleanDesignTreeNode,
) -> None:
    if parent_clean.type not in {NodeType.ROW, NodeType.COLUMN}:
        return
    if not _is_scroll_like_host(clean):
        return
    if _flex_wrap_covers_parent_axis(
        ir_node,
        parent_type=parent_clean.type,
        clean=clean,
    ):
        return
    axis = "height (wrap=expanded or fixed height)" if parent_clean.type == NodeType.COLUMN else (
        "width (wrap=expanded/flexibleLoose or fixed width)"
    )
    raise GenerationError(
        f"IR node {clean.id!r} is a scroll/grid host under {parent_clean.type.value} parent "
        f"{parent_clean.id!r} without flex bounds on {axis}; RenderFlex or viewport overflow likely"
    )


def _is_skip_control_text(
    clean: CleanDesignTreeNode,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    parent_id = parent_by_id.get(clean.id)
    if parent_id is None:
        return False
    parent = tree_by_id.get(parent_id)
    if parent is None or parent.type != NodeType.STACK:
        return False
    has_vector = any(child.type == NodeType.VECTOR for child in parent.children)
    has_numeric = any(
        child.type == NodeType.TEXT and (child.text or "").strip().isdigit() for child in parent.children
    )
    return has_vector and has_numeric


def _validate_text_contrast(
    clean: CleanDesignTreeNode,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
    parent_by_id: dict[str, str],
) -> None:
    if clean.type != NodeType.TEXT:
        return
    if _is_skip_control_text(clean, parent_by_id, tree_by_id):
        return
    foreground = clean.style.text_color
    background = nearest_ancestor_fill_hex(
        clean.id,
        tree_by_id=tree_by_id,
        parent_by_id=parent_by_id,
    )
    if not foreground or not background:
        return
    ratio = contrast_ratio(foreground, background)
    if ratio < _WCAG_AA_MIN_RATIO:
        raise GenerationError(
            f"IR text node {clean.id!r} contrast {ratio:.2f}:1 is below WCAG AA ({_WCAG_AA_MIN_RATIO}:1) "
            f"for textColor {foreground!r} on parent fill {background!r}"
        )


def _in_scroll_context(
    node_id: str,
    *,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    current = parent_by_id.get(node_id)
    while current is not None:
        ancestor = tree_by_id.get(current)
        if ancestor is None:
            break
        if ancestor.scroll_axis != "none":
            return True
        current = parent_by_id.get(current)
    return False


def _scroll_axes_for(clean: CleanDesignTreeNode) -> frozenset[str]:
    if clean.scroll_axis == "both":
        return frozenset({"vertical", "horizontal"})
    if clean.scroll_axis == "vertical":
        return frozenset({"vertical"})
    if clean.scroll_axis == "horizontal":
        return frozenset({"horizontal"})
    return frozenset()


def _ancestor_scroll_axes(
    node_id: str,
    *,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> frozenset[str]:
    axes: set[str] = set()
    current = parent_by_id.get(node_id)
    while current is not None:
        ancestor = tree_by_id.get(current)
        if ancestor is None:
            break
        axes.update(_scroll_axes_for(ancestor))
        current = parent_by_id.get(current)
    return frozenset(axes)


def _needs_nested_scroll_constraints(
    clean: CleanDesignTreeNode,
    *,
    root_id: str,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    child_axes = set(_scroll_axes_for(clean))
    if clean.type == NodeType.GRID:
        child_axes.add("vertical")
    if not child_axes:
        return False
    if child_axes & set(_ancestor_scroll_axes(clean.id, parent_by_id=parent_by_id, tree_by_id=tree_by_id)):
        return True
    parent_id = parent_by_id.get(clean.id)
    root = tree_by_id.get(root_id)
    if (
        parent_id == root_id
        and root is not None
        and root.type == NodeType.STACK
        and "vertical" in child_axes
    ):
        return True
    return False


def _apply_nested_scroll_guard(
    clean: CleanDesignTreeNode,
    *,
    root_id: str,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> None:
    if _needs_nested_scroll_constraints(
        clean,
        root_id=root_id,
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    ):
        clean.nested_scroll_constraints = True


def _apply_row_text_flex_guard(
    ir_node: WidgetIrNode,
    clean: CleanDesignTreeNode,
    *,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> None:
    if clean.type != NodeType.TEXT:
        return
    parent_id = parent_by_id.get(clean.id)
    if parent_id is None:
        return
    parent = tree_by_id.get(parent_id)
    if parent is None or parent.type != NodeType.ROW:
        return
    if ir_node.wrap in {
        FlexWrapIr.EXPANDED,
        FlexWrapIr.FLEXIBLE_LOOSE,
        FlexWrapIr.SIZED_BOX_WIDTH,
    }:
        return
    ir_node.wrap = FlexWrapIr.FLEXIBLE_LOOSE


def _node_box_size(clean: CleanDesignTreeNode) -> tuple[float | None, float | None]:
    if clean.stack_placement is not None:
        return figma_positioned_dimensions(clean, clean.stack_placement)
    width = clean.sizing.width if (clean.sizing.width or 0) > 0 else None
    height = clean.sizing.height if (clean.sizing.height or 0) > 0 else None
    return width, height


def _apply_min_touch_target_guard(clean: CleanDesignTreeNode) -> None:
    if clean.type not in _INTERACTIVE_TOUCH_TYPES:
        return
    from figma_flutter_agent.parser.interaction import looks_like_checkbox_control

    if looks_like_checkbox_control(clean):
        return
    width, height = _node_box_size(clean)
    if width is None or height is None:
        return
    if min(width, height) >= _MIN_TOUCH_TARGET_PX:
        return
    clean.min_touch_target = _MIN_TOUCH_TARGET_PX


def _validate_asset_paths(clean: CleanDesignTreeNode, project_dir: Path) -> None:
    for asset_key in (clean.vector_asset_key, clean.image_asset_key):
        if not asset_key:
            continue
        normalized = asset_key.replace("\\", "/")
        if not normalized.lower().endswith(_ASSET_SUFFIXES):
            continue
        target = project_dir / Path(normalized)
        if target.is_file():
            continue
        raise GenerationError(
            f"IR node {clean.id!r} references missing asset {normalized!r} under {project_dir}"
        )


def _node_bounds(clean: CleanDesignTreeNode) -> _Bounds | None:
    placement = clean.stack_placement
    if placement is not None:
        width, height = figma_positioned_dimensions(clean, placement)
        left = placement.left if placement.left is not None else clean.offset_x
        top = placement.top if placement.top is not None else clean.offset_y
        box_width = width if width is not None else (clean.sizing.width or 0.0)
        box_height = height if height is not None else (clean.sizing.height or 0.0)
    else:
        left = clean.offset_x
        top = clean.offset_y
        box_width = clean.sizing.width or 0.0
        box_height = clean.sizing.height or 0.0
    if box_width <= 0 or box_height <= 0:
        return None
    return left, top, left + box_width, top + box_height


def _bounds_overlap(first: _Bounds, second: _Bounds) -> bool:
    left_a, top_a, right_a, bottom_a = first
    left_b, top_b, right_b, bottom_b = second
    return left_a < right_b and left_b < right_a and top_a < bottom_b and top_b < bottom_a


def _ir_node_is_stack_host(ir_node: WidgetIrNode, clean: CleanDesignTreeNode) -> bool:
    if ir_node.kind == WidgetIrKind.STACK:
        return True
    return ir_node.kind == WidgetIrKind.AUTO and clean.type == NodeType.STACK


def _is_stack_interactive(clean: CleanDesignTreeNode, ir_node: WidgetIrNode) -> bool:
    if ir_node.kind in {WidgetIrKind.BUTTON, WidgetIrKind.INPUT}:
        return True
    return clean.type in _STACK_INTERACTIVE_TYPES


def _is_opaque_stack_occluder(clean: CleanDesignTreeNode) -> bool:
    if clean.type not in _STACK_OCCLUDER_TYPES:
        return False
    opacity = clean.style.opacity
    if opacity is not None and opacity < 0.05:
        return False
    return True


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


def _index_ir_nodes(root: WidgetIrNode) -> dict[str, WidgetIrNode]:
    return {node.figma_id: node for node in _walk_ir(root)}


def _attach_ir_child_unique(ir_parent: WidgetIrNode, ir_child: WidgetIrNode) -> bool:
    if any(existing.figma_id == ir_child.figma_id for existing in ir_parent.children):
        return False
    ir_parent.children.append(ir_child)
    return True


def _resolve_ir_host_for_clean_child(
    child_figma_id: str,
    *,
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
        return None
    return host


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
        return None
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


def validate_render_safety(root: CleanDesignTreeNode) -> None:
    """Fail-closed check for stack ghost occlusion on the deterministic path.

    Args:
        root: Canonical clean tree after guards.

    Raises:
        GenerationError: When opaque decor is painted above an interactive control.
    """
    screen_ir = default_screen_ir(root)
    tree_by_id = index_clean_tree(root)
    _validate_stack_ghost_occlusion(screen_ir.root, tree_by_id=tree_by_id)


def _validate_stack_ghost_occlusion(
    ir_node: WidgetIrNode,
    *,
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> None:
    clean = tree_by_id.get(ir_node.figma_id)
    if clean is None:
        return
    if not _ir_node_is_stack_host(ir_node, clean):
        for child in ir_node.children:
            _validate_stack_ghost_occlusion(child, tree_by_id=tree_by_id)
        return
    children = ir_node.children
    for index, ir_child in enumerate(children):
        child_clean = tree_by_id.get(ir_child.figma_id)
        if child_clean is None or not _is_stack_interactive(child_clean, ir_child):
            continue
        interactive_bounds = _node_bounds(child_clean)
        if interactive_bounds is None:
            continue
        for later in children[index + 1 :]:
            later_clean = tree_by_id.get(later.figma_id)
            if later_clean is None or not _is_opaque_stack_occluder(later_clean):
                continue
            occluder_bounds = _node_bounds(later_clean)
            if occluder_bounds is None:
                continue
            if _bounds_overlap(interactive_bounds, occluder_bounds):
                raise GenerationError(
                    f"IR stack child {later.figma_id!r} ({later_clean.type.value}) is painted "
                    f"above interactive node {ir_child.figma_id!r} and overlaps its hit region; "
                    "reorder STACK children or move the decorator below the control"
                )
    for child in ir_node.children:
        _validate_stack_ghost_occlusion(child, tree_by_id=tree_by_id)


def _input_bottom_edge(clean: CleanDesignTreeNode) -> float | None:
    bounds = _node_bounds(clean)
    if bounds is None:
        return None
    return bounds[3]


def _input_needs_keyboard_scroll_fix(
    clean: CleanDesignTreeNode,
    *,
    viewport_height: float,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    if clean.type != NodeType.INPUT:
        return False
    if clean.stack_placement is not None:
        return False
    bottom = _input_bottom_edge(clean)
    if bottom is None:
        return False
    if bottom <= viewport_height * _KEYBOARD_BOTTOM_VIEWPORT_FRACTION:
        return False
    if _in_scroll_context(clean.id, parent_by_id=parent_by_id, tree_by_id=tree_by_id):
        return False
    parent_id = parent_by_id.get(clean.id)
    if parent_id is None:
        return False
    parent = tree_by_id.get(parent_id)
    if parent is None or parent.type not in {NodeType.COLUMN, NodeType.ROW}:
        return False
    return True


def _nearest_column_scroll_host(
    node_id: str,
    *,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> CleanDesignTreeNode | None:
    current = parent_by_id.get(node_id)
    while current is not None:
        ancestor = tree_by_id.get(current)
        if ancestor is None:
            return None
        if ancestor.type == NodeType.COLUMN:
            return ancestor
        current = parent_by_id.get(current)
    return None


def _apply_keyboard_scroll_guard(
    clean: CleanDesignTreeNode,
    *,
    viewport_height: float,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> None:
    if not _input_needs_keyboard_scroll_fix(
        clean,
        viewport_height=viewport_height,
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    ):
        return
    host = _nearest_column_scroll_host(
        clean.id,
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    )
    if host is None or host.scroll_axis != "none":
        return
    host.scroll_axis = "vertical"


def _validate_keyboard_scroll_trap(
    clean: CleanDesignTreeNode,
    *,
    viewport_height: float,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> None:
    if not _input_needs_keyboard_scroll_fix(
        clean,
        viewport_height=viewport_height,
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    ):
        return
    if _in_scroll_context(clean.id, parent_by_id=parent_by_id, tree_by_id=tree_by_id):
        return
    host = _nearest_column_scroll_host(
        clean.id,
        parent_by_id=parent_by_id,
        tree_by_id=tree_by_id,
    )
    if host is not None and host.scroll_axis != "none":
        return
    raise GenerationError(
        f"IR input node {clean.id!r} sits in the lower half of a flex layout without a "
        "scroll ancestor; keyboard inset will overflow — wrap the form in a vertical scroll host"
    )


@dataclass(frozen=True)
class _TokenRegistry:
    colors: frozenset[str]
    color_by_name: dict[str, str]
    font_sizes: frozenset[float]


def _normalize_token_color(value: str) -> str | None:
    trimmed = value.strip()
    if trimmed.startswith("#") and len(trimmed) == 7:
        return f"0xFF{trimmed[1:].upper()}"
    if trimmed.lower().startswith("0x"):
        body = trimmed[2:].upper()
        if len(body) == 6:
            return f"0xFF{body}"
        if len(body) == 8:
            return f"0x{body}"
    return _normalize_hex_color(value)


def _build_token_registry(tokens: DesignTokens) -> _TokenRegistry:
    colors: set[str] = set()
    color_by_name: dict[str, str] = {}
    for name, value in tokens.colors.items():
        normalized = _normalize_token_color(value)
        if normalized is not None:
            colors.add(normalized)
            color_by_name[name] = normalized
    font_sizes: set[float] = set()
    for style in tokens.typography.values():
        font_sizes.add(round(style.font_size, 2))
    return _TokenRegistry(
        colors=frozenset(colors),
        color_by_name=color_by_name,
        font_sizes=frozenset(font_sizes),
    )


def _collect_clean_tree_token_colors(root: CleanDesignTreeNode) -> frozenset[str]:
    """Colors observed on parsed nodes (Figma truth beyond deduped flat token keys)."""
    colors: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        style = node.style
        for raw in (
            style.text_color,
            style.background_color,
            style.border_color,
        ):
            if raw is None:
                continue
            normalized = _normalize_token_color(raw)
            if normalized is not None:
                colors.add(normalized)
        for child in node.children:
            walk(child)

    walk(root)
    return frozenset(colors)


def _collect_clean_tree_font_sizes(root: CleanDesignTreeNode) -> frozenset[float]:
    """Font sizes observed on parsed text nodes (Figma truth beyond deduped typography)."""
    sizes: set[float] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        font_size = node.style.font_size
        if font_size is not None and font_size > 0:
            sizes.add(round(font_size, 2))
        for child in node.children:
            walk(child)

    walk(root)
    return frozenset(sizes)


def _merge_token_registry_with_clean_tree(
    registry: _TokenRegistry,
    root: CleanDesignTreeNode,
) -> _TokenRegistry:
    """Allow IR overrides to reference colors and font sizes present on the clean tree."""
    extra_colors = _collect_clean_tree_token_colors(root)
    extra_font_sizes = _collect_clean_tree_font_sizes(root)
    if not extra_colors and not extra_font_sizes:
        return registry
    return _TokenRegistry(
        colors=registry.colors | extra_colors,
        color_by_name=registry.color_by_name,
        font_sizes=registry.font_sizes | extra_font_sizes,
    )


def _resolve_token_color(value: str, registry: _TokenRegistry) -> str | None:
    trimmed = value.strip()
    by_name = registry.color_by_name.get(trimmed)
    if by_name is not None:
        return by_name
    normalized = _normalize_token_color(trimmed)
    if normalized is not None and normalized in registry.colors:
        return normalized
    return _nearest_token_color(trimmed, registry)


def _color_rgb(hex_literal: str) -> tuple[int, int, int] | None:
    normalized = _normalize_token_color(hex_literal)
    if normalized is None:
        return None
    channels = normalized.removeprefix("0x").removeprefix("0X")
    if len(channels) != 8:
        return None
    value = int(channels, 16)
    return (value >> 16) & 255, (value >> 8) & 255, value & 255


def _nearest_token_color(value: str, registry: _TokenRegistry) -> str | None:
    source = _color_rgb(value)
    if source is None or not registry.colors:
        return None
    best: str | None = None
    best_distance = float("inf")
    for candidate in registry.colors:
        target = _color_rgb(candidate)
        if target is None:
            continue
        distance = sum(abs(source[index] - target[index]) for index in range(3))
        if distance < best_distance:
            best_distance = distance
            best = candidate
    if best is None or best_distance > _MAX_COLOR_SNAP_CHANNEL_DELTA * 3:
        return None
    return best


def _nearest_token_font_size(value: float, registry: _TokenRegistry) -> float | None:
    if not registry.font_sizes:
        return None
    nearest = min(registry.font_sizes, key=lambda size: abs(size - value))
    if abs(nearest - value) > _FONT_SIZE_SNAP_TOLERANCE:
        return None
    return nearest


def _snap_ir_overrides_to_tokens(
    overrides: WidgetIrOverrides,
    *,
    figma_id: str,
    registry: _TokenRegistry,
) -> WidgetIrOverrides:
    updates: dict[str, object] = {}
    if overrides.text_color is not None:
        resolved = _resolve_token_color(overrides.text_color, registry)
        if resolved is None:
            raise GenerationError(
                f"IR overrides for {figma_id!r} textColor {overrides.text_color!r} "
                "is not a registered design token color"
            )
        if resolved != overrides.text_color:
            updates["text_color"] = resolved
    if overrides.background_color is not None:
        resolved = _resolve_token_color(overrides.background_color, registry)
        if resolved is None:
            raise GenerationError(
                f"IR overrides for {figma_id!r} backgroundColor "
                f"{overrides.background_color!r} is not a registered design token color"
            )
        if resolved != overrides.background_color:
            updates["background_color"] = resolved
    if overrides.font_size is not None:
        rounded = round(overrides.font_size, 2)
        if rounded in registry.font_sizes:
            if rounded != overrides.font_size:
                updates["font_size"] = rounded
        else:
            snapped = _nearest_token_font_size(overrides.font_size, registry)
            if snapped is None:
                raise GenerationError(
                    f"IR overrides for {figma_id!r} fontSize {overrides.font_size} "
                    "is not a registered typography token size"
                )
            updates["font_size"] = snapped
    if not updates:
        return overrides
    return overrides.model_copy(update=updates)


def _viewport_box_metrics(
    clean: CleanDesignTreeNode,
    placement: StackPlacement,
) -> tuple[float, float, float, float] | None:
    width, height = figma_positioned_dimensions(clean, placement)
    left = placement.left if placement.left is not None else clean.offset_x
    top = placement.top if placement.top is not None else clean.offset_y
    box_width = width if width is not None else (clean.sizing.width or 0.0)
    box_height = height if height is not None else (clean.sizing.height or 0.0)
    if box_width <= 0 or box_height <= 0:
        return None
    return left, top, box_width, box_height


def _clamp_viewport_bounds(
    clean: CleanDesignTreeNode,
    *,
    viewport_width: float,
    viewport_height: float,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> bool:
    """Shift ``stackPlacement`` so positioned nodes fit the root viewport (non-scroll)."""
    placement = clean.stack_placement
    if placement is None:
        return False
    if _in_scroll_context(clean.id, parent_by_id=parent_by_id, tree_by_id=tree_by_id):
        return False
    metrics = _viewport_box_metrics(clean, placement)
    if metrics is None:
        return False
    left, top, box_width, box_height = metrics
    margin = _VIEWPORT_OVERFLOW_MARGIN_PX
    new_left = left
    new_top = top
    if new_left < -margin:
        new_left = -margin
    if new_left + box_width > viewport_width + margin:
        new_left = viewport_width + margin - box_width
    if new_top < -margin:
        new_top = -margin
    if new_top + box_height > viewport_height + margin:
        new_top = viewport_height + margin - box_height
    center_x = new_left + box_width / 2.0
    center_y = new_top + box_height / 2.0
    min_center_x = margin
    max_center_x = viewport_width - margin
    min_center_y = margin
    max_center_y = viewport_height - margin
    if center_x < min_center_x:
        new_left += min_center_x - center_x
    elif center_x > max_center_x:
        new_left -= center_x - max_center_x
    if center_y < min_center_y:
        new_top += min_center_y - center_y
    elif center_y > max_center_y:
        new_top -= center_y - max_center_y
    if abs(new_left - left) < 0.5 and abs(new_top - top) < 0.5:
        return False
    clean.stack_placement = placement.model_copy(update={"left": new_left, "top": new_top})
    return True


def _validate_viewport_bounds(
    clean: CleanDesignTreeNode,
    *,
    viewport_width: float,
    viewport_height: float,
    root_id: str,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> None:
    placement = clean.stack_placement
    if placement is None:
        return
    if parent_by_id.get(clean.id) != root_id:
        return
    if _in_scroll_context(clean.id, parent_by_id=parent_by_id, tree_by_id=tree_by_id):
        return
    metrics = _viewport_box_metrics(clean, placement)
    if metrics is None:
        return
    left, top, box_width, box_height = metrics
    center_x = left + box_width / 2.0
    center_y = top + box_height / 2.0
    margin = _VIEWPORT_OVERFLOW_MARGIN_PX
    if (
        center_x < -margin
        or center_x > viewport_width + margin
        or center_y < -margin
        or center_y > viewport_height + margin
    ):
        raise GenerationError(
            f"IR node {clean.id!r} center ({center_x:.1f}, {center_y:.1f}) lies outside the "
            f"{viewport_width:.0f}x{viewport_height:.0f} root frame without a scroll ancestor; "
            "likely hallucinated stackPlacement coordinates"
        )


def apply_ir_guards(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
    *,
    tokens: DesignTokens | None = None,
) -> CleanDesignTreeNode:
    """Apply render-safety guards on a tree copy; return normalized clean tree (INV-2).

    The input ``root`` is never mutated; callers must use the returned tree for emit.
    """
    from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree

    working = deep_copy_clean_tree(root)
    _apply_ir_guards_inplace(screen_ir, working, tokens=tokens)
    return working


def _apply_ir_guards_inplace(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
    *,
    tokens: DesignTokens | None = None,
) -> None:
    """Mutate ``root`` in place for render safety (internal; use ``apply_ir_guards``)."""
    tree_by_id = index_clean_tree(root)
    parent_by_id = _build_parent_map(root)
    viewport = _viewport_size(root)
    root_id = screen_ir.root.figma_id
    token_registry = _build_token_registry(tokens) if tokens is not None else None
    if token_registry is not None:
        token_registry = _merge_token_registry_with_clean_tree(token_registry, root)

    realign_screen_ir_children_to_clean_tree(screen_ir, root)
    _align_ir_stack_children_to_clean_tree(screen_ir.root, tree_by_id=tree_by_id)

    for ir_node in _walk_ir(screen_ir.root):
        clean = tree_by_id.get(ir_node.figma_id)
        if clean is None:
            continue
        if ir_node.overrides is not None and token_registry is not None:
            ir_node.overrides = _snap_ir_overrides_to_tokens(
                ir_node.overrides,
                figma_id=ir_node.figma_id,
                registry=token_registry,
            )
        _apply_nested_scroll_guard(
            clean,
            root_id=root_id,
            parent_by_id=parent_by_id,
            tree_by_id=tree_by_id,
        )
        _apply_row_text_flex_guard(
            ir_node,
            clean,
            parent_by_id=parent_by_id,
            tree_by_id=tree_by_id,
        )
        _apply_min_touch_target_guard(clean)
        if viewport is not None:
            viewport_width, viewport_height = viewport
            _apply_keyboard_scroll_guard(
                clean,
                viewport_height=viewport_height,
                parent_by_id=parent_by_id,
                tree_by_id=tree_by_id,
            )

    from figma_flutter_agent.generator.ir.states import apply_screen_ir_states_and_rules

    apply_screen_ir_states_and_rules(
        screen_ir,
        root,
        viewport_width=viewport[0] if viewport is not None else None,
    )

    if viewport is not None:
        viewport_width, viewport_height = viewport
        root_frame_id = root.id
        for node_id, clean in tree_by_id.items():
            if parent_by_id.get(node_id) != root_frame_id:
                continue
            if _clamp_viewport_bounds(
                clean,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                parent_by_id=parent_by_id,
                tree_by_id=tree_by_id,
            ):
                logger.warning(
                    "Clamped stackPlacement for {} to fit {:.0f}x{:.0f} viewport",
                    node_id,
                    viewport_width,
                    viewport_height,
                )


def validate_screen_ir(
    screen_ir: ScreenIr,
    root: CleanDesignTreeNode,
    *,
    extracted_widget_names: frozenset[str] | None = None,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
    apply_guards: bool = True,
    skip_presence_normalize: bool = False,
    layout_source: str | None = None,
    strict_invariants: bool = False,
) -> CleanDesignTreeNode:
    """Validate IR; optionally normalize tree via guards.

    Returns:
        The clean tree to use for emit (guarded copy when ``apply_guards`` is true,
        otherwise the original ``root``).

    Raises:
        GenerationError: When IR references unknown nodes or unsafe render structure.
    """
    if apply_guards:
        root = apply_ir_guards(screen_ir, root, tokens=tokens)
    else:
        realign_screen_ir_children_to_clean_tree(screen_ir, root)

    tree_by_id = index_clean_tree(root)
    parent_by_id = _build_parent_map(root)
    viewport = _viewport_size(root)
    omit = frozenset(screen_ir.omit_figma_ids)
    extracted = extracted_widget_names or frozenset()

    _validate_ir_graph_integrity(screen_ir.root)
    if not apply_guards:
        _align_ir_stack_children_to_clean_tree(screen_ir.root, tree_by_id=tree_by_id)
    _validate_stack_ghost_occlusion(screen_ir.root, tree_by_id=tree_by_id)

    if screen_ir.root.figma_id not in tree_by_id:
        raise GenerationError(f"screenIr.root figmaId {screen_ir.root.figma_id!r} not in clean tree")
    if screen_ir.root.figma_id in omit:
        raise GenerationError("screenIr.root cannot appear in omitFigmaIds")

    for rule in screen_ir.adaptive_rules:
        if rule.figma_id not in tree_by_id:
            raise GenerationError(
                f"screenIr adaptiveRules figmaId {rule.figma_id!r} not in clean tree"
            )
        if _find_parent_ir(screen_ir.root, rule.figma_id) is None:
            raise GenerationError(
                f"screenIr adaptiveRules figmaId {rule.figma_id!r} not present in screenIr graph"
            )

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
        if placement is not None and not _has_stack_ancestor(
            clean.id,
            parent_by_id=parent_by_id,
            tree_by_id=tree_by_id,
        ):
            raise GenerationError(
                f"node {ir_node.figma_id!r} has stackPlacement but no STACK ancestor in cleanTree"
            )
        _validate_stack_placement_bounds(clean)
        parent_id = parent_by_id.get(ir_node.figma_id)
        if parent_id is not None:
            parent_clean = tree_by_id.get(parent_id)
            if parent_clean is not None:
                _validate_flex_child_slot(ir_node, clean, parent_clean)
        _validate_text_contrast(
            clean,
            tree_by_id=tree_by_id,
            parent_by_id=parent_by_id,
        )
        if project_dir is not None:
            _validate_asset_paths(clean, project_dir)
        if viewport is not None:
            viewport_width, viewport_height = viewport
            _validate_viewport_bounds(
                clean,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                root_id=root.id,
                parent_by_id=parent_by_id,
                tree_by_id=tree_by_id,
            )
            _validate_keyboard_scroll_trap(
                clean,
                viewport_height=viewport_height,
                parent_by_id=parent_by_id,
                tree_by_id=tree_by_id,
            )

    if screen_ir.root.figma_id == root.id:
        from figma_flutter_agent.generator.ir.presence import validate_stack_visual_ir_coverage

        validate_stack_visual_ir_coverage(
            screen_ir,
            root,
            extracted_widget_names=extracted_widget_names,
            skip_presence_normalize=skip_presence_normalize,
        )
    from figma_flutter_agent.generator.geometry.invariants.reporting import (
        raise_on_hard_geometry_violations,
    )
    from figma_flutter_agent.generator.geometry.invariants.validate import (
        validate_geometry_invariants,
    )

    geometry_violations = validate_geometry_invariants(
        root,
        layout_source=layout_source,
        strict_invariants=strict_invariants,
    )
    raise_on_hard_geometry_violations(geometry_violations, context="ir_validate")
    return root


def validate_extracted_widget_ir(
    widget: ExtractedWidget,
    root: CleanDesignTreeNode,
    *,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> None:
    """Raise when an extracted widget IR subtree is invalid against ``root``."""
    if widget.widget_ir is None:
        return
    tree_by_id = index_clean_tree(root)
    if widget.widget_ir.figma_id not in tree_by_id:
        logger.warning(
            "Skipping widgetIr validation for {}: figmaId {} absent from clean tree "
            "(likely true_subtree_pruning); rely on deterministic lib/widgets code",
            widget.widget_name,
            widget.widget_ir.figma_id,
        )
        return
    validate_screen_ir(
        ScreenIr(root=widget.widget_ir),
        root,
        extracted_widget_names=frozenset({widget.widget_name}),
        project_dir=project_dir,
        tokens=tokens,
    )


def validate_extracted_widgets(
    widgets: list[ExtractedWidget],
    root: CleanDesignTreeNode,
    *,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
) -> None:
    for widget in widgets:
        validate_extracted_widget_ir(widget, root, project_dir=project_dir, tokens=tokens)


def _find_parent_ir(node: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    for child in node.children:
        if child.figma_id == figma_id:
            return node
        found = _find_parent_ir(child, figma_id)
        if found is not None:
            return found
    return None

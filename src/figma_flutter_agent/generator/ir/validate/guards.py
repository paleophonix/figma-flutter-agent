"""IR guard application: scroll, flex, touch-target, keyboard, asset, and occlusion checks."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.tree import default_screen_ir, index_clean_tree
from figma_flutter_agent.generator.ir.validate.graph import (
    _ir_node_is_stack_host,
    _is_opaque_stack_occluder,
    _is_stack_interactive,
)
from figma_flutter_agent.generator.layout.widgets import figma_positioned_dimensions
from figma_flutter_agent.parser.accessibility import contrast_ratio, nearest_ancestor_fill_hex
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FlexWrapIr,
    NodeType,
    SizingMode,
    WidgetIrNode,
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

_Bounds = tuple[float, float, float, float]


def _record_guard_mutation(
    *,
    node_id: str,
    field: str,
    old: object,
    new: object,
    transform: str,
    policy: str | None = None,
) -> None:
    from figma_flutter_agent.debug.provenance import get_provenance_recorder

    recorder = get_provenance_recorder()
    if recorder is None:
        return
    recorder.record_mutation(
        checkpoint="CP1_guards",
        transform=transform,
        node_id=node_id,
        field=field,
        old=old,
        new=new,
        policy=policy,
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
        return bool(_is_scroll_like_host(clean) and clean.sizing.height_mode != SizingMode.FILL)
    if parent_type == NodeType.ROW:
        if wrap == FlexWrapIr.FLEXIBLE_LOOSE:
            return True
        if wrap == FlexWrapIr.SIZED_BOX_WIDTH:
            return True
        return bool(clean.sizing.width_mode == SizingMode.FIXED and (clean.sizing.width or 0) > 0)
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
    return bool(parent_id == root_id and root is not None and root.type == NodeType.STACK and "vertical" in child_axes)


def _apply_nested_scroll_guard(
    clean: CleanDesignTreeNode,
    *,
    root_id: str,
    parent_by_id: dict[str, str],
    tree_by_id: dict[str, CleanDesignTreeNode],
) -> None:
    if (
        _needs_nested_scroll_constraints(
            clean,
            root_id=root_id,
            parent_by_id=parent_by_id,
            tree_by_id=tree_by_id,
        )
        and not clean.nested_scroll_constraints
    ):
        clean.nested_scroll_constraints = True
        _record_guard_mutation(
            node_id=clean.id,
            field="nested_scroll_constraints",
            old=False,
            new=True,
            transform="nested_scroll_guard",
        )


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
    previous = ir_node.wrap
    ir_node.wrap = FlexWrapIr.FLEXIBLE_LOOSE
    _record_guard_mutation(
        node_id=clean.id,
        field="wrap",
        old=previous.value if previous else None,
        new=ir_node.wrap.value,
        transform="row_text_flex_guard",
    )


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
    _record_guard_mutation(
        node_id=clean.id,
        field="min_touch_target",
        old=None,
        new=_MIN_TOUCH_TARGET_PX,
        transform="min_touch_target_guard",
    )


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
    return not (parent is None or parent.type not in {NodeType.COLUMN, NodeType.ROW})


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
    previous = host.scroll_axis
    host.scroll_axis = "vertical"
    _record_guard_mutation(
        node_id=host.id,
        field="scroll_axis",
        old=previous,
        new="vertical",
        transform="keyboard_scroll_guard",
    )


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

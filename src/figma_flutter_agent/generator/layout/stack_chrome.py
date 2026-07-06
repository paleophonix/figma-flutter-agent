"""Stack layering helpers for docked bottom navigation chrome."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets.positioned import (
    _stack_has_bottom_anchored_child,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_VIEWPORT_PARTITION_MIN_SCROLLABLE_BODY = 64.0


def stack_child_needs_viewport_pin_outside_scroll(
    child: CleanDesignTreeNode,
    parent_stack: CleanDesignTreeNode,
) -> bool:
    """Return True when bottom chrome must stay viewport-fixed outside scroll."""
    if child.type == NodeType.BOTTOM_NAV:
        return True
    from figma_flutter_agent.parser.stack_paint import (
        _is_bottom_nav_interactive,
        _viewport_size,
    )

    if parent_stack.type != NodeType.STACK:
        return False
    viewport_width, viewport_height = _viewport_size(parent_stack.children)
    return _is_bottom_nav_interactive(
        child,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
    )


def partition_viewport_pinned_stack_layers(
    stack_node: CleanDesignTreeNode,
    child_nodes: list[CleanDesignTreeNode],
    child_widgets: list[str],
) -> tuple[list[str], list[str]] | None:
    """Split a root absolute stack into scrollable artboard vs viewport-pinned nav."""
    if not _stack_has_bottom_anchored_child(stack_node):
        return None
    pinned_indices = [
        index
        for index, child in enumerate(child_nodes)
        if stack_child_needs_viewport_pin_outside_scroll(child, stack_node)
    ]
    if not pinned_indices or len(pinned_indices) == len(child_nodes):
        return None
    clearance = bottom_chrome_clearance_height(stack_node)
    stack_height = float(stack_node.sizing.height or 0.0)
    if stack_height <= clearance + _VIEWPORT_PARTITION_MIN_SCROLLABLE_BODY:
        return None
    scroll_widgets = [
        widget for index, widget in enumerate(child_widgets) if index not in pinned_indices
    ]
    pinned_widgets = [child_widgets[index] for index in pinned_indices]
    if not scroll_widgets or not pinned_widgets:
        return None
    return scroll_widgets, pinned_widgets


def is_bottom_docked_stack_child(child: CleanDesignTreeNode) -> bool:
    """Return True when a stack child is bottom navigation chrome."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        is_viewport_chrome_band,
    )

    if is_viewport_chrome_band(child):
        return False
    if child.type == NodeType.BOTTOM_NAV:
        return True
    placement = child.stack_placement
    if placement is None:
        return False
    return placement.vertical == "BOTTOM"


def stack_flow_child_is_trailing_chrome(child: CleanDesignTreeNode) -> bool:
    """Return True when shared-scroll flow columns pin a slot after body content.

    Bottom navigation and the iOS home-indicator band must trail scrollable body
    panels instead of appearing ahead of the shared scroll host.
    """
    if is_bottom_docked_stack_child(child):
        return True
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        _viewport_chrome_vertical_role,
    )

    return _viewport_chrome_vertical_role(child) == "BOTTOM"


def bottom_chrome_clearance_height(stack: CleanDesignTreeNode) -> float:
    """Return scroll inset for content layered under docked bottom chrome."""
    chrome_height = 0.0
    for child in stack.children:
        if not is_bottom_docked_stack_child(child):
            continue
        placement = child.stack_placement
        height = (placement.height if placement is not None else None) or child.sizing.height or 0.0
        chrome_height = max(chrome_height, float(height))
    padding_bottom = stack.padding.bottom if stack.padding is not None else 0.0
    return max(chrome_height, float(padding_bottom))


def column_hoists_docked_bottom_nav_stack(node: CleanDesignTreeNode) -> bool:
    """Return True when a column root hosts a single stack with bottom chrome."""
    if node.type != NodeType.COLUMN or len(node.children) != 1:
        return False
    child = node.children[0]
    return child.type == NodeType.STACK and _stack_has_bottom_anchored_child(child)


def _bounded_growable_scroll_position(child: CleanDesignTreeNode) -> str | None:
    """Return bounded ``Positioned`` pins when a growable panel must not blanket the stack."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_is_growable_panel,
    )
    from figma_flutter_agent.generator.layout.widgets.positioned import _positioned_fields

    if not stack_child_is_growable_panel(child):
        return None
    placement = child.stack_placement
    if placement is None:
        return None
    fields = _positioned_fields(placement, render_boundary=child.render_boundary)
    if not fields:
        return None
    joined = ", ".join(fields)
    has_vertical_pin = any(token in joined for token in ("top:", "bottom:", "height:"))
    if not has_vertical_pin:
        return None
    return joined


def _shared_body_scroll_position_fields(
    stack_node: CleanDesignTreeNode,
    body_children: list[CleanDesignTreeNode],
) -> str:
    """Return ``Positioned`` pins for one scroll host spanning sequential body panels."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_ordinal_top,
    )

    clearance = bottom_chrome_clearance_height(stack_node)
    top = min(stack_child_ordinal_top(child) for child in body_children)
    top_lit = format_geometry_literal(top)
    bottom_lit = format_geometry_literal(clearance)
    return f"left: 0.0, right: 0.0, top: {top_lit}, bottom: {bottom_lit}"


def _shared_body_scroll_inner_column(
    body_pairs: list[tuple[CleanDesignTreeNode, str]],
) -> str:
    """Compose growable body panels into one intrinsic ``Column`` for a shared scroll host."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_ordinal_bottom,
        stack_child_ordinal_top,
    )

    parts: list[str] = []
    for index, (child, widget) in enumerate(body_pairs):
        if index > 0:
            previous_child = body_pairs[index - 1][0]
            gap = stack_child_ordinal_top(child) - stack_child_ordinal_bottom(previous_child)
            if gap > 0.5:
                parts.append(f"SizedBox(height: {format_geometry_literal(gap)})")
        parts.append(widget)
    inner = ", ".join(parts) or "const SizedBox.shrink()"
    return (
        "Column(mainAxisSize: MainAxisSize.min, "
        f"crossAxisAlignment: CrossAxisAlignment.stretch, children: [{inner}])"
    )


def canonicalize_root_bottom_nav_terminal_overlay(
    root: CleanDesignTreeNode,
) -> CleanDesignTreeNode:
    """Move docked bottom navigation to the terminal paint slot on root stacks."""
    if root.type != NodeType.STACK or not root.children:
        return root
    nav_indices = [
        index for index, child in enumerate(root.children) if is_bottom_docked_stack_child(child)
    ]
    if not nav_indices:
        return root
    nav_index = nav_indices[-1]
    if nav_index == len(root.children) - 1:
        return root
    children = list(root.children)
    nav = children.pop(nav_index)
    children.append(nav)
    return root.model_copy(update={"children": children})


def _position_pin_bottom_stack_layer(
    child: CleanDesignTreeNode,
    widget: str,
    *,
    parent_stack: CleanDesignTreeNode,
) -> str:
    """Wrap decomposed stack slots that pin-bottom chrome left without ``Positioned``."""
    stripped = widget.strip()
    if stripped.startswith("Positioned("):
        return widget
    placement = child.stack_placement
    if placement is None:
        return widget
    from figma_flutter_agent.generator.layout.widgets.positioned import (
        _positioned_fields,
        sanitize_positioned_axis_fields,
    )

    parent_height = float(parent_stack.sizing.height or 0.0) or None
    fields = sanitize_positioned_axis_fields(
        _positioned_fields(
            placement,
            render_boundary=child.render_boundary,
            parent_height=parent_height,
        )
    )
    if not fields:
        return widget
    return f"Positioned({', '.join(fields)}, child: {widget})"


def apply_pin_bottom_chrome_to_stack_layers(
    stack_node: CleanDesignTreeNode,
    child_nodes: list[CleanDesignTreeNode],
    child_widgets: list[str],
    *,
    allow_outward_paint: bool = False,
) -> list[str]:
    """Wrap non-bottom stack layers in a fill scroll host for docked bottom chrome."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_stack_numeric_glyph_overlay_host,
        stack_flow_child_is_shared_scroll_body,
        stack_uses_shared_body_scroll_host,
    )

    if layout_fact_stack_numeric_glyph_overlay_host(stack_node):
        return child_widgets
    if not _stack_has_bottom_anchored_child(stack_node):
        return child_widgets
    clearance = bottom_chrome_clearance_height(stack_node)
    uses_shared_scroll = stack_uses_shared_body_scroll_host(stack_node)
    pinned: list[str] = []
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        is_viewport_chrome_band,
        stack_child_should_use_pin_bottom_scroll_host,
    )

    scroll_body_pairs: list[tuple[CleanDesignTreeNode, str]] = []

    def flush_shared_scroll() -> None:
        if not scroll_body_pairs:
            return
        inner_column = _shared_body_scroll_inner_column(scroll_body_pairs)
        clip = "clipBehavior: Clip.none, " if allow_outward_paint else ""
        padding = (
            f"padding: const EdgeInsets.only(bottom: {format_geometry_literal(clearance)}), "
            if clearance > 0
            else ""
        )
        scroll = f"SingleChildScrollView({clip}{padding}child: {inner_column})"
        bounds = _shared_body_scroll_position_fields(
            stack_node,
            [child for child, _ in scroll_body_pairs],
        )
        pinned.append(f"Positioned({bounds}, child: {scroll})")
        scroll_body_pairs.clear()

    for child, widget in zip(child_nodes, child_widgets, strict=True):
        if uses_shared_scroll and stack_flow_child_is_shared_scroll_body(child, stack_node):
            scroll_body_pairs.append((child, widget))
            continue
        if uses_shared_scroll:
            flush_shared_scroll()
        if is_bottom_docked_stack_child(child):
            pinned.append(
                _position_pin_bottom_stack_layer(
                    child,
                    widget,
                    parent_stack=stack_node,
                )
            )
            continue
        if is_viewport_chrome_band(child):
            pinned.append(
                _position_pin_bottom_stack_layer(
                    child,
                    widget,
                    parent_stack=stack_node,
                )
            )
            continue
        if not stack_child_should_use_pin_bottom_scroll_host(child, parent_stack=stack_node):
            pinned.append(
                _position_pin_bottom_stack_layer(
                    child,
                    widget,
                    parent_stack=stack_node,
                )
            )
            continue
        pinned.append(
            pin_bottom_scroll_layer_expr(
                widget,
                allow_outward_paint=allow_outward_paint,
                bottom_padding=clearance,
                child=child,
            )
        )
    if uses_shared_scroll:
        flush_shared_scroll()
    return pinned


def pin_bottom_scroll_layer_expr(
    widget_expr: str,
    *,
    allow_outward_paint: bool = False,
    bottom_padding: float = 0.0,
    child: CleanDesignTreeNode | None = None,
) -> str:
    """Wrap a decomposed stack layer in the scroll host used for bottom chrome."""
    clip = "clipBehavior: Clip.none, " if allow_outward_paint else ""
    padding = (
        f"padding: const EdgeInsets.only(bottom: {format_geometry_literal(bottom_padding)}), "
        if bottom_padding > 0
        else ""
    )
    scroll = f"SingleChildScrollView({clip}{padding}child: {widget_expr})"
    if child is not None:
        bounds = _bounded_growable_scroll_position(child)
        if bounds is not None:
            return f"Positioned({bounds}, child: {scroll})"
    return f"Positioned.fill(child: {scroll})"


def pin_bottom_flow_column_scroll_wrap(
    widget_expr: str,
    *,
    allow_outward_paint: bool = False,
    bottom_padding: float = 0.0,
) -> str:
    """Wrap a flow-column stack slot in ``Expanded`` + ``SingleChildScrollView``."""
    clip = "clipBehavior: Clip.none, " if allow_outward_paint else ""
    padding = (
        f"padding: const EdgeInsets.only(bottom: {format_geometry_literal(bottom_padding)}), "
        if bottom_padding > 0
        else ""
    )
    return f"Expanded(child: SingleChildScrollView({clip}{padding}child: {widget_expr}))"

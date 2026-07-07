"""Private builder method planning for large layout files."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.layout.common import to_pascal_case
from figma_flutter_agent.generator.layout.style import box_decoration_expr
from figma_flutter_agent.generator.layout.widgets import (
    _stack_has_bottom_anchored_child,
    _wrap_root_stack_viewport,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.parser.render_bounds import stack_needs_soft_clip
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

MAX_INLINE_LAYOUT_DEPTH = 7


def _bound_column_wallpaper_lead(
    lead: str,
    tree: CleanDesignTreeNode,
) -> str:
    """Bound wallpaper Stack height when it leads a column root.

    A ``Column`` with ``mainAxisSize.min`` passes unbounded main-axis max extent
    to non-flex children; wallpaper backgrounds are ``Stack`` hosts and require a
    finite height before paint.
    """
    from figma_flutter_agent.generator.artboard import resolve_artboard_height

    height = resolve_artboard_height(tree)
    if height is None or height <= 0:
        return lead
    height_token = format_geometry_literal(height)
    return f"SizedBox(width: double.infinity, height: {height_token}, child: {lead})"


def _wrap_column_flow_child_call(
    child: CleanDesignTreeNode,
    call: str,
    *,
    parent_node: CleanDesignTreeNode,
    responsive_enabled: bool,
) -> str:
    """Bound finite-height column slots before paint (chrome bands, stack sections)."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_flow_child_needs_vertical_extent_bind,
        stack_flow_child_vertical_extent_wrap,
    )

    if stack_flow_child_needs_vertical_extent_bind(
        child,
        parent_node=parent_node,
        responsive_enabled=responsive_enabled,
    ):
        call = stack_flow_child_vertical_extent_wrap(
            child,
            call,
            parent_node=parent_node,
        )
    return call


@dataclass(frozen=True)
class LayoutMethod:
    """Private builder method extracted from a deep layout tree."""

    name: str
    node: CleanDesignTreeNode


def _tree_depth(node: CleanDesignTreeNode, depth: int = 1) -> int:
    if not node.children:
        return depth
    return max(_tree_depth(child, depth + 1) for child in node.children)


def _layout_method_name(node: CleanDesignTreeNode) -> str:
    base = to_pascal_case(node.name) or f"Section{node.id.replace(':', '')}"
    return f"_build{base}"


def chunk_dart_file_stem(feature_name: str, class_name: str) -> str:
    """Return the file stem for a chunk Dart file."""
    suffix = class_name.lower().removeprefix("figmachunk")
    return f"{feature_name}_chunk_{suffix}"


def method_node_suppresses_compose_flex_fill(
    node: CleanDesignTreeNode,
    render_tree: CleanDesignTreeNode,
) -> bool:
    """Return True when compose owns flex fill for a decomposed phone-shell slot.

    Decomposed builder methods for FILL-height growable panels must not emit a
    top-level ``Expanded`` when compose wraps the method call in a bounded slot
    (``SizedBox`` / ``Align`` and optional outer ``Expanded``).
    """
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_is_growable_panel,
    )

    _ = render_tree
    return (
        stack_child_is_growable_panel(node)
        and node.sizing.height_mode == SizingMode.FILL
    )


def strip_top_level_flex_parent_data(widget: str) -> str:
    """Remove a single outer ``Expanded``/``Flexible`` wrapper from ``widget``."""
    from figma_flutter_agent.generator.layout.flex_policy.wrap import (
        _unwrap_flex_parent_data_wrapper,
    )

    unwrapped = _unwrap_flex_parent_data_wrapper(widget.strip())
    if unwrapped is None:
        return widget
    return unwrapped[1]


def plan_layout_methods(tree: CleanDesignTreeNode) -> list[LayoutMethod] | None:
    """Split deep layout trees into per-child private builder methods."""
    if _tree_depth(tree) <= MAX_INLINE_LAYOUT_DEPTH:
        return None
    if (
        tree.type not in {NodeType.STACK, NodeType.COLUMN, NodeType.ROW}
        or not tree.children
    ):
        return None
    used: set[str] = set()
    methods: list[LayoutMethod] = []
    for index, child in enumerate(tree.children):
        name = _layout_method_name(child)
        if name in used:
            name = f"{name}{index + 1}"
        used.add(name)
        methods.append(LayoutMethod(name=name, node=child))
    return methods


def _stack_method_call_expr(
    method: LayoutMethod,
    *,
    pin_bottom_chrome: bool,
    parent_stack: CleanDesignTreeNode | None = None,
    column_flow: bool = False,
    allow_outward_paint: bool = False,
    bottom_padding: float = 0.0,
) -> str:
    """Wrap a decomposed stack layer for scroll + bottom-anchored chrome."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        stack_child_should_use_pin_bottom_scroll_host,
    )
    from figma_flutter_agent.generator.layout.stack_chrome import (
        is_bottom_docked_stack_child,
        pin_bottom_scroll_layer_expr,
    )

    call = f"{method.name}(context)"
    if not pin_bottom_chrome:
        return call
    if is_bottom_docked_stack_child(method.node):
        return call
    if not stack_child_should_use_pin_bottom_scroll_host(
        method.node,
        parent_stack=parent_stack,
    ):
        return call
    if column_flow:
        clip = "clipBehavior: Clip.none, " if allow_outward_paint else ""
        padding = (
            f"padding: const EdgeInsets.only(bottom: {format_geometry_literal(bottom_padding)}), "
            if bottom_padding > 0
            else ""
        )
        return f"Expanded(child: SingleChildScrollView({clip}{padding}child: {call}))"
    return pin_bottom_scroll_layer_expr(
        call,
        allow_outward_paint=allow_outward_paint,
        bottom_padding=bottom_padding,
        child=method.node,
    )


def compose_decomposed_root_widget(
    tree: CleanDesignTreeNode,
    methods: list[LayoutMethod],
    *,
    responsive_enabled: bool,
    theme_variant: str = "material_3",
    suppress_root_fill: bool = False,
    artboard_background_lead: str | None = None,
) -> str:
    """Compose the root widget expression from extracted builder methods."""
    pin_bottom_chrome = (
        tree.type == NodeType.STACK and _stack_has_bottom_anchored_child(tree)
    )
    allow_outward_paint = stack_needs_soft_clip(tree)
    from figma_flutter_agent.generator.layout.stack_chrome import (
        bottom_chrome_clearance_height,
    )

    bottom_padding = bottom_chrome_clearance_height(tree) if pin_bottom_chrome else 0.0
    child_call_parts: list[str] = []
    for child, method in zip(tree.children, methods, strict=True):
        call = _stack_method_call_expr(
            method,
            pin_bottom_chrome=pin_bottom_chrome,
            parent_stack=tree,
            allow_outward_paint=allow_outward_paint,
            bottom_padding=bottom_padding,
        )
        if tree.type == NodeType.COLUMN:
            call = _wrap_column_flow_child_call(
                child,
                call,
                parent_node=tree,
                responsive_enabled=responsive_enabled,
            )
        child_call_parts.append(call)
    if artboard_background_lead:
        wallpaper_lead = artboard_background_lead
        if tree.type == NodeType.COLUMN:
            wallpaper_lead = _bound_column_wallpaper_lead(wallpaper_lead, tree)
        child_call_parts.insert(0, wallpaper_lead)
    child_calls = ", ".join(child_call_parts) or "const SizedBox.shrink()"
    viewport_pinned_layers: list[str] | None = None
    preview_stack_widget: str | None = None
    if tree.type == NodeType.STACK:
        from figma_flutter_agent.generator.layout.flex_policy import (
            stack_child_ordinal_bottom,
            stack_child_ordinal_top,
            stack_flow_child_horizontal_wrap,
            stack_flow_child_vertical_extent_wrap,
            stack_should_flow_as_column,
        )

        if stack_should_flow_as_column(tree) and artboard_background_lead is None:
            from figma_flutter_agent.generator.layout.flex_policy.stack import (
                _stack_is_phone_shell_layout,
                is_viewport_chrome_band,
                stack_child_is_growable_panel,
                stack_flow_child_is_shared_scroll_body,
                stack_flow_column_child_sort_key,
                stack_uses_shared_body_scroll_host,
            )
            from figma_flutter_agent.generator.layout.stack_chrome import (
                is_bottom_docked_stack_child,
                stack_flow_child_is_trailing_chrome,
            )

            growable_panels = sum(
                1 for child in tree.children if stack_child_is_growable_panel(child)
            )
            is_phone_shell = _stack_is_phone_shell_layout(
                tree,
                growable_panels=growable_panels,
            )
            uses_shared_scroll = (
                pin_bottom_chrome
                and stack_uses_shared_body_scroll_host(
                    tree, growable_panels=growable_panels
                )
            )
            ordered = sorted(
                zip(tree.children, methods, strict=True),
                key=lambda pair: stack_flow_column_child_sort_key(pair[0]),
            )
            flow_parts: list[str] = []
            scroll_body_parts: list[str] = []
            trailing_parts: list[str] = []
            for index, (child, method) in enumerate(ordered):
                gap_expr: str | None = None
                if index > 0:
                    previous_child = ordered[index - 1][0]
                    gap = stack_child_ordinal_top(child) - stack_child_ordinal_bottom(
                        previous_child
                    )
                    if gap > 0.5:
                        gap_expr = f"SizedBox(height: {format_geometry_literal(gap)})"
                widget = f"{method.name}(context)"
                widget = stack_flow_child_horizontal_wrap(child, widget)
                from figma_flutter_agent.generator.layout.flex_policy.stack import (
                    stack_child_should_use_pin_bottom_scroll_host,
                    stack_flow_child_needs_vertical_extent_bind,
                )
                from figma_flutter_agent.generator.layout.stack_chrome import (
                    pin_bottom_flow_column_scroll_wrap,
                )

                if stack_flow_child_needs_vertical_extent_bind(
                    child,
                    parent_node=tree,
                    responsive_enabled=responsive_enabled,
                ):
                    widget = stack_flow_child_vertical_extent_wrap(
                        child, widget, parent_node=tree
                    )
                is_scroll_body = (
                    uses_shared_scroll
                    and stack_flow_child_is_shared_scroll_body(child, tree)
                )
                is_trailing = (
                    uses_shared_scroll and stack_flow_child_is_trailing_chrome(child)
                )
                if not uses_shared_scroll:
                    if (
                        pin_bottom_chrome
                        and responsive_enabled
                        and not is_viewport_chrome_band(child)
                        and not is_bottom_docked_stack_child(child)
                        and stack_child_should_use_pin_bottom_scroll_host(
                            child, parent_stack=tree
                        )
                    ):
                        widget = pin_bottom_flow_column_scroll_wrap(
                            widget,
                            allow_outward_paint=allow_outward_paint,
                            bottom_padding=bottom_padding,
                        )
                    if (
                        responsive_enabled
                        and is_phone_shell
                        and not is_viewport_chrome_band(child)
                        and stack_child_is_growable_panel(child)
                        and "Expanded(" not in widget
                    ):
                        widget = f"Expanded(child: {widget})"
                from figma_flutter_agent.generator.layout.flex_policy.wrap import (
                    repair_flex_parent_data_order,
                )

                widget = repair_flex_parent_data_order(widget)
                if is_scroll_body:
                    if gap_expr is not None:
                        scroll_body_parts.append(gap_expr)
                    scroll_body_parts.append(widget)
                elif is_trailing:
                    if gap_expr is not None:
                        trailing_parts.append(gap_expr)
                    trailing_parts.append(widget)
                else:
                    if gap_expr is not None:
                        flow_parts.append(gap_expr)
                    flow_parts.append(widget)
            if uses_shared_scroll and scroll_body_parts:
                inner_body = ", ".join(scroll_body_parts) or "const SizedBox.shrink()"
                inner_column = (
                    "Column(mainAxisSize: MainAxisSize.min, "
                    f"crossAxisAlignment: CrossAxisAlignment.stretch, children: [{inner_body}])"
                )
                flow_parts.append(
                    pin_bottom_flow_column_scroll_wrap(
                        inner_column,
                        allow_outward_paint=allow_outward_paint,
                        bottom_padding=bottom_padding,
                    )
                )
            flow_parts.extend(trailing_parts)
            if artboard_background_lead:
                flow_parts.insert(
                    0,
                    _bound_column_wallpaper_lead(artboard_background_lead, tree),
                )
            main_axis = (
                "mainAxisSize: MainAxisSize.max, "
                if (pin_bottom_chrome or is_phone_shell) and responsive_enabled
                else "mainAxisSize: MainAxisSize.min, "
            )
            widget = (
                "Column("
                f"{main_axis}"
                "crossAxisAlignment: CrossAxisAlignment.stretch, "
                f"children: [{', '.join(flow_parts)}]"
                ")"
            )
        else:
            from figma_flutter_agent.generator.layout.stack_chrome import (
                apply_pin_bottom_chrome_to_stack_layers,
                partition_viewport_pinned_stack_layers,
            )

            child_nodes = [method.node for method in methods]
            child_widgets = [f"{method.name}(context)" for method in methods]
            layered_children = (
                apply_pin_bottom_chrome_to_stack_layers(
                    tree,
                    child_nodes,
                    child_widgets,
                    allow_outward_paint=allow_outward_paint,
                )
                if pin_bottom_chrome
                else child_widgets
            )
            stack_clip = (
                "Clip.hardEdge"
                if artboard_background_lead
                else ("Clip.none" if stack_needs_soft_clip(tree) else "Clip.hardEdge")
            )
            preview_layers = list(layered_children)
            if artboard_background_lead:
                preview_layers.insert(
                    0,
                    f"Positioned.fill(child: {artboard_background_lead})",
                )
            if pin_bottom_chrome:
                partition = partition_viewport_pinned_stack_layers(
                    tree,
                    child_nodes,
                    layered_children,
                )
                if partition is not None:
                    scroll_widgets, viewport_pinned_layers = partition
                    stack_layers = list(scroll_widgets)
                    if artboard_background_lead:
                        stack_layers.insert(
                            0,
                            f"Positioned.fill(child: {artboard_background_lead})",
                        )
                    child_calls = ", ".join(stack_layers) or "const SizedBox.shrink()"
                    preview_stack_widget = (
                        f"Stack(clipBehavior: {stack_clip}, "
                        f"children: [{', '.join(preview_layers)}])"
                    )
                else:
                    stack_layers = preview_layers
                    child_calls = ", ".join(stack_layers) or "const SizedBox.shrink()"
            else:
                stack_layers = preview_layers
                child_calls = ", ".join(stack_layers) or "const SizedBox.shrink()"
            widget = f"Stack(clipBehavior: {stack_clip}, children: [{child_calls}])"
        root_decoration = box_decoration_expr(
            tree.style,
            width=tree.sizing.width,
            height=tree.sizing.height,
        )
        if root_decoration is not None and not suppress_root_fill:
            widget = f"Container(decoration: {root_decoration}, child: {widget})"
        return _wrap_root_stack_viewport(
            tree,
            widget,
            is_layout_root=True,
            responsive_enabled=responsive_enabled,
            viewport_pinned_layers=viewport_pinned_layers,
            preview_stack_widget=preview_stack_widget,
        )
    if tree.type == NodeType.COLUMN:
        from figma_flutter_agent.generator.layout.flex_policy.stack import (
            _column_is_phone_shell_layout,
            is_viewport_chrome_band,
            stack_child_is_growable_panel,
        )
        from figma_flutter_agent.generator.layout.stack_chrome import (
            column_hoists_docked_bottom_nav_stack,
        )
        from figma_flutter_agent.generator.layout.widgets import (
            _wrap_root_column_viewport,
        )

        growable_panels = sum(
            1 for child in tree.children if stack_child_is_growable_panel(child)
        )
        is_phone_shell = _column_is_phone_shell_layout(
            tree,
            growable_panels=growable_panels,
        )
        if is_phone_shell and len(methods) >= 2:
            flow_parts: list[str] = []
            for child, method in zip(tree.children, methods, strict=True):
                call = f"{method.name}(context)"
                call = _wrap_column_flow_child_call(
                    child,
                    call,
                    parent_node=tree,
                    responsive_enabled=responsive_enabled,
                )
                if (
                    not is_viewport_chrome_band(child)
                    and stack_child_is_growable_panel(child)
                    and "Expanded(" not in call
                ):
                    call = f"Expanded(child: {call})"
                flow_parts.append(call)
            viewport_child = (
                "Column(mainAxisSize: MainAxisSize.max, "
                "crossAxisAlignment: CrossAxisAlignment.stretch, "
                f"children: [{', '.join(flow_parts)}])"
            )
        elif column_hoists_docked_bottom_nav_stack(tree) and len(methods) == 1:
            viewport_child = child_calls
        else:
            viewport_child = (
                "Column(mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.stretch, "
                f"children: [{child_calls}])"
            )
        from figma_flutter_agent.generator.layout.scroll import (
            wrap_flex_auto_layout_padding,
        )

        viewport_child = wrap_flex_auto_layout_padding(tree, viewport_child)
        return _wrap_root_column_viewport(
            tree,
            viewport_child,
            responsive_enabled=responsive_enabled,
            theme_variant=theme_variant,
        )
    if tree.type == NodeType.ROW:
        return f"Row(children: [{child_calls}])"
    return child_calls

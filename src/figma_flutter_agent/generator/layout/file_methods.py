"""Private builder method planning for large layout files."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.layout.style import box_decoration_expr
from figma_flutter_agent.generator.layout.widgets import (
    _stack_has_bottom_anchored_child,
    _wrap_root_stack_viewport,
)
from figma_flutter_agent.generator.layout.common import to_pascal_case
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.parser.render_bounds import stack_needs_soft_clip
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

MAX_INLINE_LAYOUT_DEPTH = 7


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
    allow_outward_paint: bool = False,
    bottom_padding: float = 0.0,
) -> str:
    """Wrap a decomposed stack layer for scroll + bottom-anchored chrome."""
    from figma_flutter_agent.generator.layout.stack_chrome import (
        is_bottom_docked_stack_child,
        pin_bottom_scroll_layer_expr,
    )

    call = f"{method.name}(context)"
    if not pin_bottom_chrome:
        return call
    if is_bottom_docked_stack_child(method.node):
        return call
    return pin_bottom_scroll_layer_expr(
        call,
        allow_outward_paint=allow_outward_paint,
        bottom_padding=bottom_padding,
    )


def compose_decomposed_root_widget(
    tree: CleanDesignTreeNode,
    methods: list[LayoutMethod],
    *,
    responsive_enabled: bool,
    theme_variant: str = "material_3",
) -> str:
    """Compose the root widget expression from extracted builder methods."""
    pin_bottom_chrome = tree.type == NodeType.STACK and _stack_has_bottom_anchored_child(
        tree
    )
    allow_outward_paint = stack_needs_soft_clip(tree)
    from figma_flutter_agent.generator.layout.stack_chrome import (
        bottom_chrome_clearance_height,
    )

    bottom_padding = bottom_chrome_clearance_height(tree) if pin_bottom_chrome else 0.0
    child_calls = (
        ", ".join(
            _stack_method_call_expr(
                method,
                pin_bottom_chrome=pin_bottom_chrome,
                allow_outward_paint=allow_outward_paint,
                bottom_padding=bottom_padding,
            )
            for method in methods
        )
        or "const SizedBox.shrink()"
    )
    if tree.type == NodeType.STACK:
        from figma_flutter_agent.generator.layout.flex_policy import (
            stack_child_ordinal_bottom,
            stack_child_ordinal_top,
            stack_flow_child_horizontal_wrap,
            stack_flow_child_vertical_extent_wrap,
            stack_should_flow_as_column,
        )

        if stack_should_flow_as_column(tree):
            ordered = sorted(
                zip(tree.children, methods, strict=True),
                key=lambda pair: (stack_child_ordinal_top(pair[0]), pair[0].id),
            )
            flow_parts: list[str] = []
            for index, (child, method) in enumerate(ordered):
                if index > 0:
                    previous_child = ordered[index - 1][0]
                    gap = stack_child_ordinal_top(child) - stack_child_ordinal_bottom(
                        previous_child
                    )
                    if gap > 0.5:
                        flow_parts.append(
                            f"SizedBox(height: {format_geometry_literal(gap)})"
                        )
                widget = _stack_method_call_expr(
                    method,
                    pin_bottom_chrome=pin_bottom_chrome,
                    allow_outward_paint=allow_outward_paint,
                    bottom_padding=bottom_padding,
                )
                widget = stack_flow_child_horizontal_wrap(child, widget)
                widget = stack_flow_child_vertical_extent_wrap(child, widget)
                flow_parts.append(widget)
            widget = (
                "Column("
                "mainAxisSize: MainAxisSize.min, "
                "crossAxisAlignment: CrossAxisAlignment.stretch, "
                f"children: [{', '.join(flow_parts)}]"
                ")"
            )
        else:
            stack_clip = "Clip.none" if stack_needs_soft_clip(tree) else "Clip.hardEdge"
            widget = f"Stack(clipBehavior: {stack_clip}, children: [{child_calls}])"
        root_decoration = box_decoration_expr(
            tree.style,
            width=tree.sizing.width,
            height=tree.sizing.height,
        )
        if root_decoration is not None:
            widget = f"Container(decoration: {root_decoration}, child: {widget})"
        return _wrap_root_stack_viewport(
            tree,
            widget,
            is_layout_root=True,
            responsive_enabled=responsive_enabled,
        )
    if tree.type == NodeType.COLUMN:
        from figma_flutter_agent.generator.layout.stack_chrome import (
            column_hoists_docked_bottom_nav_stack,
        )
        from figma_flutter_agent.generator.layout.widgets import _wrap_root_column_viewport

        if column_hoists_docked_bottom_nav_stack(tree) and len(methods) == 1:
            viewport_child = child_calls
        else:
            viewport_child = (
                "Column(crossAxisAlignment: CrossAxisAlignment.stretch, "
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

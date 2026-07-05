"""Form controls rendering for Dart layout generation."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.style import box_decoration_expr, dart_color_expr
from figma_flutter_agent.generator.variant.actions import button_on_pressed_expr
from figma_flutter_agent.generator.variant.controls import (
    input_decoration_expr,
    render_checkbox_widget,
    render_cupertino_button_widget,
    render_dialog_widget,
    render_dropdown_widget,
    render_material_button_widget,
    render_radio_group_widget,
    render_radio_widget,
    render_slider_widget,
    render_switch_widget,
)
from figma_flutter_agent.generator.variant.state import (
    input_enabled_expr,
    input_obscure_text_expr,
)
from figma_flutter_agent.parser.interaction import layout_fact_checkbox_control
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode


def wrap_material_input_child(widget: str, *, theme_variant: str) -> str:
    """Wrap ``TextField`` with a ``Material`` ancestor (required by Flutter Material)."""
    if theme_variant == "cupertino":
        return widget
    return f"Material(color: Colors.transparent, child: {widget})"


def render_checkbox(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    selection_stack: CleanDesignTreeNode | None = None,
) -> str:
    if layout_fact_checkbox_control(node):
        from figma_flutter_agent.generator.layout.interactive_toggle import (
            render_stateful_toggle_checkbox,
        )

        return render_stateful_toggle_checkbox(node, selection_stack=selection_stack)
    label = escape_dart_string(node.accessibility_label or node.name)
    semantics_label = label
    control = render_checkbox_widget(label=label, node=node, theme_variant=theme_variant)
    return f"Semantics(label: '{semantics_label}', child: {control})"


def render_switch(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_switch_widget(label=label, node=node, theme_variant=theme_variant)
    return f"Semantics(label: '{label}', child: {control})"


def render_segmented_control_host(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    theme_variant: str,
) -> str:
    """Render a stateful segmented pill host with mutually exclusive option labels."""
    from figma_flutter_agent.generator.layout.flex_policy.row import (
        _segmented_option_label_text,
        layout_fact_segmented_option_host,
    )
    from figma_flutter_agent.generator.layout.style import box_decoration_expr
    from figma_flutter_agent.generator.variant.state import variant_is_checked
    from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal

    _ = theme_variant
    label = escape_dart_string(node.accessibility_label or node.name)
    option_nodes = [child for child in node.children if layout_fact_segmented_option_host(child)]
    option_labels = [
        escaped
        for child in option_nodes
        if (escaped := escape_dart_string(_segmented_option_label_text(child) or ""))
    ]
    if len(option_labels) < 2:
        body = ", ".join(child_widgets) or "const SizedBox.shrink()"
        row = (
            f"Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [{body}])"
            if node.spacing and node.spacing > 0
            else f"Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [{body}])"
        )
    else:
        selected_index = 0
        for index, child in enumerate(option_nodes):
            if variant_is_checked(child):
                selected_index = index
                break
        labels_literal = ", ".join(f"'{item}'" for item in option_labels)
        row = (
            "_SegmentedPillControl("
            f"labels: const [{labels_literal}], "
            f"initialIndex: {selected_index}"
            ")"
        )
    decoration = box_decoration_expr(
        node.style,
        width=node.sizing.width,
        height=node.sizing.height,
    )
    if decoration is not None:
        width = node.sizing.width
        height = node.sizing.height
        size_fields: list[str] = []
        if width is not None and width > 0:
            size_fields.append(f"width: {format_geometry_literal(float(width))}")
        if height is not None and height > 0:
            size_fields.append(f"height: {format_geometry_literal(float(height))}")
        size_prefix = ", ".join(size_fields)
        if size_prefix:
            row = f"Container({size_prefix}, decoration: {decoration}, child: {row})"
        else:
            row = f"Container(decoration: {decoration}, child: {row})"
    return f"Semantics(label: '{label}', child: {row})"


def render_radio_group(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_radio_group_widget(node=node, theme_variant=theme_variant)
    return f"Semantics(label: '{label}', child: {control})"


def render_radio(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_node: CleanDesignTreeNode | None = None,
    ancestor_hosts: tuple[CleanDesignTreeNode, ...] | None = None,
    uses_svg: bool = True,
) -> str:
    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_compact_radio_glyph,
        radio_external_semantic_label,
    )

    compact_glyph = layout_fact_compact_radio_glyph(
        node,
        parent_node,
        ancestor_hosts=ancestor_hosts,
    )
    external_label = radio_external_semantic_label(
        node,
        parent_node,
        ancestor_hosts=ancestor_hosts,
    )
    fallback = escape_dart_string(node.accessibility_label or node.name)
    label = escape_dart_string(external_label) if external_label else fallback
    control = render_radio_widget(
        label=label,
        node=node,
        theme_variant=theme_variant,
        compact_glyph=compact_glyph,
        uses_svg=uses_svg,
    )
    return f"Semantics(label: '{label}', child: {control})"


def render_dropdown(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_dropdown_widget(node=node, theme_variant=theme_variant)
    decoration = box_decoration_expr(
        node.style,
        width=node.sizing.width,
        height=node.sizing.height,
    )
    if decoration is not None:
        size_fields: list[str] = []
        width = node.sizing.width
        height = node.sizing.height
        if width is not None and width > 0:
            size_fields.append(f"width: {format_geometry_literal(float(width))}")
        if height is not None and height > 0:
            size_fields.append(f"height: {format_geometry_literal(float(height))}")
        size_prefix = ", ".join(size_fields)
        horizontal_pad = 12.0
        if node.padding is not None and node.padding.left is not None and node.padding.left > 0:
            horizontal_pad = float(node.padding.left)
        pad_expr = format_geometry_literal(horizontal_pad)
        if size_prefix:
            control = (
                f"Container({size_prefix}, decoration: {decoration}, "
                f"alignment: Alignment.centerLeft, "
                f"padding: EdgeInsets.symmetric(horizontal: {pad_expr}), "
                f"child: {control})"
            )
        else:
            control = f"Container(decoration: {decoration}, child: {control})"
    return f"Semantics(label: '{label}', child: {control})"


def render_dialog(
    node: CleanDesignTreeNode,
    child_widgets: list[str],
    *,
    theme_variant: str,
) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_dialog_widget(
        title=label,
        child_widgets=child_widgets,
        theme_variant=theme_variant,
    )
    return f"Semantics(label: '{label}', child: {control})"


def render_slider(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_slider_widget(label=label, node=node, theme_variant=theme_variant)
    return f"Semantics(label: '{label}', child: {control})"


def render_button(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    on_pressed = button_on_pressed_expr(node)
    if theme_variant == "cupertino":
        button = render_cupertino_button_widget(
            label=label,
            on_pressed=on_pressed,
            node=node,
        )
    else:
        bg_color = dart_color_expr(node.style, fallback="AppColors.color2")
        button = render_material_button_widget(
            label=label,
            on_pressed=on_pressed,
            background_color=bg_color,
            node=node,
        )
    return f"Semantics(label: '{label}', child: {button})"


def render_input(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    enabled = input_enabled_expr(node)
    obscure = input_obscure_text_expr(node)
    if theme_variant == "cupertino":
        return (
            f"Semantics("
            f"label: '{label}', "
            f"child: CupertinoTextField("
            f"enabled: {enabled}, "
            f"obscureText: {obscure}, "
            f"placeholder: '{label}'"
            f")"
            f")"
        )
    decoration = input_decoration_expr(node, label=label)
    field = f"TextField(enabled: {enabled}, obscureText: {obscure}, decoration: {decoration})"
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    return f"Semantics(label: '{label}', child: {field})"

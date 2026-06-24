"""Form controls rendering for Dart layout generation."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.style import dart_color_expr
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
from figma_flutter_agent.schemas import CleanDesignTreeNode


def wrap_material_input_child(widget: str, *, theme_variant: str) -> str:
    """Wrap ``TextField`` with a ``Material`` ancestor (required by Flutter Material)."""
    if theme_variant == "cupertino":
        return widget
    return f"Material(color: Colors.transparent, child: {widget})"


def render_checkbox(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    if layout_fact_checkbox_control(node):
        from figma_flutter_agent.generator.layout.interactive_toggle import (
            render_stateful_toggle_checkbox,
        )

        return render_stateful_toggle_checkbox(node)
    label = escape_dart_string(node.accessibility_label or node.name)
    semantics_label = label
    control = render_checkbox_widget(label=label, node=node, theme_variant=theme_variant)
    return f"Semantics(label: '{semantics_label}', child: {control})"


def render_switch(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_switch_widget(label=label, node=node, theme_variant=theme_variant)
    return f"Semantics(label: '{label}', child: {control})"


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
    )
    return f"Semantics(label: '{label}', child: {control})"


def render_dropdown(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_dropdown_widget(node=node, theme_variant=theme_variant)
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

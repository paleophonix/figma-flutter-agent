"""Form controls rendering for Dart layout generation."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_common import escape_dart_string
from figma_flutter_agent.generator.layout_style import dart_color_expr
from figma_flutter_agent.generator.variant_props import (
    button_on_pressed_expr,
    input_decoration_expr,
    input_enabled_expr,
    input_obscure_text_expr,
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
from figma_flutter_agent.schemas import CleanDesignTreeNode


def render_checkbox(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_checkbox_widget(label=label, node=node, theme_variant=theme_variant)
    return f"Semantics(label: '{label}', child: {control})"


def render_switch(node: CleanDesignTreeNode, *, theme_variant: str) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_switch_widget(label=label, node=node, theme_variant=theme_variant)
    return f"Semantics(label: '{label}', child: {control})"


def render_radio_group(node: CleanDesignTreeNode) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_radio_group_widget(node=node)
    return f"Semantics(label: '{label}', child: {control})"


def render_radio(node: CleanDesignTreeNode) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_radio_widget(label=label, node=node)
    return f"Semantics(label: '{label}', child: {control})"


def render_dropdown(node: CleanDesignTreeNode) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_dropdown_widget(node=node)
    return f"Semantics(label: '{label}', child: {control})"


def render_dialog(node: CleanDesignTreeNode, child_widgets: list[str]) -> str:
    label = escape_dart_string(node.accessibility_label or node.name)
    control = render_dialog_widget(title=label, child_widgets=child_widgets)
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
    else:
        decoration = input_decoration_expr(node, label=label)
        return (
            f"Semantics("
            f"label: '{label}', "
            f"child: TextField("
            f"enabled: {enabled}, "
            f"obscureText: {obscure}, "
            f"decoration: {decoration}"
            f")"
            f")"
        )

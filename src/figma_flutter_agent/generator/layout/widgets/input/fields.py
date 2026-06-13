"""Top-level input/textarea field widget emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.form import wrap_material_input_child
from figma_flutter_agent.generator.layout.style import (
    box_decoration_expr,
    text_style_expr,
)
from figma_flutter_agent.parser.interaction import (
    input_field_label_node,
    input_flex_value_text,
    input_hint_implies_obscure_text,
    input_hint_node,
    input_hint_text,
    input_surface_node,
    interaction_surface_node,
    looks_like_password_field_stack,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..finalize import _finalize_widget
from ..shared import _node_layout_size
from .decoration import _input_text_style_expr, _stack_input_decoration
from .icons import _render_input_trailing_suffix_icon


def _wrap_input_with_external_label(
    node: CleanDesignTreeNode,
    field_widget: str,
    *,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Stack a caption label above a bordered ``TextField`` when Figma places it outside."""
    label_node = input_field_label_node(node)
    if label_node is None:
        return field_widget
    label_text = escape_dart_string((label_node.text or "").strip())
    label_style = text_style_expr(
        label_node,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    label_widget = f"Text('{label_text}', style: {label_style})"
    return (
        "Column("
        "crossAxisAlignment: CrossAxisAlignment.start, "
        "mainAxisSize: MainAxisSize.min, "
        f"children: [{label_widget}, {field_widget}])"
    )


def _prefilled_input_field_expr(
    *,
    escaped_value: str,
    obscure: str,
    input_style: str,
    decoration: str,
    keyboard_type: str | None = None,
) -> str:
    """Emit a stateless prefilled input without per-build ``TextEditingController``."""
    keyboard = f"keyboardType: {keyboard_type}, " if keyboard_type else ""
    return (
        f"TextFormField("
        f"initialValue: '{escaped_value}', "
        f"{keyboard}"
        f"obscureText: {obscure}, "
        f"style: {input_style}, decoration: {decoration})"
    )


def _render_stack_input(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    embed_in_trailing_row: bool = False,
) -> str:
    """Render a positioned ``TextField`` for classic absolute input groups."""
    surface = input_surface_node(node) or interaction_surface_node(node)
    hint_node = input_hint_node(node)
    hint = input_hint_text(node)
    width, height = _node_layout_size(surface or node, node.stack_placement)
    field_height = surface.sizing.height if surface is not None else height
    vertical_center = field_height is not None and field_height > 0
    decoration = _stack_input_decoration(
        surface,
        hint_node,
        hint,
        host_node=node,
        field_height=field_height,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        surface_on_container=surface is not None
        and surface.style.background_color is not None,
        vertical_center=vertical_center,
    )
    obscure = (
        "true"
        if looks_like_password_field_stack(node) or input_hint_implies_obscure_text(hint)
        else "false"
    )
    input_style = _input_text_style_expr(
        node,
        hint_node=hint_node,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    value_text = input_flex_value_text(node)
    if value_text:
        escaped_value = escape_dart_string(value_text)
        field = _prefilled_input_field_expr(
            escaped_value=escaped_value,
            obscure=obscure,
            input_style=input_style,
            decoration=decoration,
        )
    else:
        field = f"TextField(obscureText: {obscure}, style: {input_style}, decoration: {decoration})"
    if not embed_in_trailing_row:
        box_decoration = (
            box_decoration_expr(
                surface.style,
                width=surface.sizing.width,
                height=surface.sizing.height,
            )
            if surface is not None
            else None
        )
        if (
            box_decoration is not None
            and width is not None
            and width > 0
            and height is not None
            and height > 0
        ):
            field = (
                f"Container("
                f"width: {width}, height: {height}, "
                f"decoration: {box_decoration}, "
                f"child: {field}"
                f")"
            )
        elif width is not None and width > 0 and height is not None and height > 0:
            field = f"SizedBox(width: {width}, height: {height}, child: {field})"
        elif width is not None and width > 0:
            field = f"SizedBox(width: {width}, child: {field})"
    elif height is not None and height > 0:
        field = f"SizedBox(height: {height}, child: {field})"
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    field = _wrap_input_with_external_label(
        node,
        field,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    label = escape_dart_string(node.accessibility_label or input_hint_text(node))
    field = f"Semantics(label: '{label}', child: {field})"
    return _finalize_widget(node, field, parent_type=parent_type)


def _render_textarea_field(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
) -> str:
    """Render a multiline ``TextField`` for Figma Textarea shells."""
    from figma_flutter_agent.generator.layout.scroll import padding_edge_insets
    from figma_flutter_agent.parser.interaction import textarea_hint_node

    hint_node = textarea_hint_node(node)
    hint_raw = (hint_node.text if hint_node is not None else None) or node.accessibility_label or "Comment"
    hint = escape_dart_string(hint_raw)
    input_style = (
        text_style_expr(
            hint_node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        if hint_node is not None
        else "Theme.of(context).textTheme.bodyMedium"
    )
    height = node.sizing.height
    min_lines = 3
    if height is not None and float(height) >= 120.0:
        min_lines = 4
    content_padding = padding_edge_insets(node) or "const EdgeInsets.fromLTRB(16.0, 12.0, 16.0, 12.0)"
    field = (
        f"TextField("
        f"maxLines: null, "
        f"minLines: {min_lines}, "
        f"style: {input_style}, "
        f"decoration: InputDecoration("
        f"hintText: '{hint}', "
        f"border: InputBorder.none, "
        f"contentPadding: {content_padding}"
        f"))"
    )
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    box_decoration = box_decoration_expr(
        node.style,
        width=node.sizing.width,
        height=node.sizing.height,
    )
    if box_decoration is not None:
        field = f"Container(decoration: {box_decoration}, child: {field})"
    if height is not None and float(height) > 0:
        field = f"SizedBox(height: {format_geometry_literal(float(height))}, child: {field})"
    label = escape_dart_string(node.accessibility_label or hint_raw)
    return _finalize_widget(
        node,
        f"Semantics(label: '{label}', child: {field})",
        parent_type=parent_type,
    )


def _render_flex_input_with_trailing_chrome(
    node: CleanDesignTreeNode,
    trailing: list[CleanDesignTreeNode],
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    uses_svg: bool,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Render prefilled flex inputs; display rows hug value copy like profile fields."""
    surface = input_surface_node(node)
    hint_node = input_hint_node(node)
    value_text = input_flex_value_text(node)
    width, height = _node_layout_size(surface or node, node.stack_placement)

    suffix_icon = _render_input_trailing_suffix_icon(
        trailing[0],
        uses_svg=uses_svg,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    hint = input_hint_text(node)
    field_height = surface.sizing.height if surface is not None else height
    vertical_center = field_height is not None and field_height > 0
    decoration = _stack_input_decoration(
        surface,
        hint_node,
        hint,
        host_node=node,
        field_height=field_height,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        surface_on_container=surface is not None
        and surface.style.background_color is not None,
        suffix_icon=suffix_icon,
        vertical_center=vertical_center,
    )
    obscure = (
        "true"
        if looks_like_password_field_stack(node) or input_hint_implies_obscure_text(hint)
        else "false"
    )
    input_style = _input_text_style_expr(
        node,
        hint_node=hint_node,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if value_text:
        escaped_value = escape_dart_string(value_text)
        field = _prefilled_input_field_expr(
            escaped_value=escaped_value,
            obscure=obscure,
            input_style=input_style,
            decoration=decoration,
        )
    else:
        field = f"TextField(obscureText: {obscure}, style: {input_style}, decoration: {decoration})"
    if height is not None and height > 0:
        field = f"SizedBox(height: {height}, child: {field})"
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    box_decoration = (
        box_decoration_expr(
            surface.style,
            width=surface.sizing.width,
            height=surface.sizing.height,
        )
        if surface is not None
        else None
    )
    if (
        box_decoration is not None
        and width is not None
        and width > 0
        and height is not None
        and height > 0
    ):
        composed = (
            f"Container(width: {width}, height: {height}, "
            f"decoration: {box_decoration}, child: {field})"
        )
    else:
        composed = field
    composed = _wrap_input_with_external_label(
        node,
        composed,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    label_node = input_field_label_node(node)
    label_raw = (label_node.text if label_node is not None else None) or node.accessibility_label or input_hint_text(node)
    label = escape_dart_string(label_raw)
    return _finalize_widget(
        node,
        f"Semantics(label: '{label}', child: {composed})",
        parent_type=parent_type,
    )

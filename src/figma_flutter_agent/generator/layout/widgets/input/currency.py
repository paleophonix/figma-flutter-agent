"""Prefix-labeled currency input row emitter."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.form import wrap_material_input_child
from figma_flutter_agent.generator.layout.style import (
    text_style_expr,
    text_widget_trailing_params,
)
from figma_flutter_agent.parser.interaction import (
    input_hint_node,
    input_hint_text,
    input_surface_node,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..layout import _flex_spacing_field
from .decoration import _input_text_style_expr, _stack_input_decoration
from .fields import _prefilled_input_field_expr


def try_render_prefix_labeled_currency_row(
    row: CleanDesignTreeNode,
    *,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Render ``label + numeric field + currency`` rows such as cash-change inputs."""
    from figma_flutter_agent.parser.interaction import input_flex_value_text
    from figma_flutter_agent.parser.interaction.forms import (
        _hosts_single_line_text_leaf,
        row_hosts_prefix_labeled_currency_input,
    )

    if not row_hosts_prefix_labeled_currency_input(row):
        return None
    input_node = next(child for child in row.children if child.type == NodeType.INPUT)
    label_leaf = next(
        leaf
        for child in row.children
        if (leaf := _hosts_single_line_text_leaf(child)) is not None
        and "₽" not in (leaf.text or "")
    )
    currency_leaf = next(
        (
            leaf
            for child in row.children
            if (leaf := _hosts_single_line_text_leaf(child)) is not None
            and "₽" in (leaf.text or "")
        ),
        None,
    )
    label_text = escape_dart_string(label_leaf.text or label_leaf.name)
    label_style = text_style_expr(
        label_leaf,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        omit_line_height=True,
    )
    label_trailing = text_widget_trailing_params(
        label_leaf.style,
        omit_strut=True,
        optical_center=True,
    )
    value_text = input_flex_value_text(input_node)
    value_style = _input_text_style_expr(
        input_node,
        hint_node=input_hint_node(input_node),
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    decoration = _stack_input_decoration(
        input_surface_node(input_node),
        input_hint_node(input_node),
        value_text or input_hint_text(input_node),
        host_node=input_node,
        field_height=input_node.sizing.height,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        surface_on_container=True,
        vertical_center=True,
    )
    if value_text:
        field = _prefilled_input_field_expr(
            escaped_value=escape_dart_string(value_text),
            obscure="false",
            input_style=value_style,
            decoration=decoration,
            keyboard_type="TextInputType.number",
        )
    else:
        field = (
            f"TextField(keyboardType: TextInputType.number, "
            f"style: {value_style}, decoration: {decoration})"
        )
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    height = row.sizing.height
    if height is not None and float(height) > 0:
        field = (
            f"SizedBox(height: {format_geometry_literal(float(height))}, "
            f"child: Center(child: {field}))"
        )
    parts = [
        f"Text('{label_text}', style: {label_style}, {label_trailing})",
        f"Expanded(child: {field})",
    ]
    if currency_leaf is not None:
        currency = escape_dart_string(currency_leaf.text or "₽")
        currency_style = text_style_expr(
            currency_leaf,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
            omit_line_height=True,
        )
        currency_trailing = text_widget_trailing_params(
            currency_leaf.style,
            omit_strut=True,
            optical_center=True,
        )
        parts.append(f"Text('{currency}', style: {currency_style}, {currency_trailing})")
    spacing_field = _flex_spacing_field(row)
    return (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"{spacing_field}"
        f"children: [{', '.join(parts)}]"
        ")"
    )

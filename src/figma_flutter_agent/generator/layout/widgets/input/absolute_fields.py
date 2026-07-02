"""Emit interactive fields from decomposed absolute painted shells."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.form import wrap_material_input_child
from figma_flutter_agent.generator.layout.style import box_decoration_expr, text_style_expr
from figma_flutter_agent.parser.interaction.absolute_fields import (
    find_field_shell_value_text,
    layout_fact_painted_field_shell_container,
    layout_fact_painted_multiline_field_shell,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..finalize import _finalize_widget
from .fields import _compose_fixed_height_input_surface, _prefilled_input_field_expr


def _keyboard_type_for_value_text(value_text: str) -> str | None:
    stripped = value_text.strip()
    if stripped.startswith("$"):
        return "TextInputType.number"
    return None


def render_decomposed_absolute_field(
    shell: CleanDesignTreeNode,
    value_node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    flow_column_child: bool = False,
) -> str:
    """Render a positioned TextField for a painted shell plus in-bounds value text."""
    multiline = layout_fact_painted_multiline_field_shell(shell)
    value_text = (value_node.text or "").strip()
    escaped_value = escape_dart_string(value_text)
    width = shell.sizing.width
    height = shell.sizing.height
    box_decoration = box_decoration_expr(
        shell.style,
        width=width,
        height=height,
    )
    input_style = text_style_expr(
        value_node,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    keyboard_type = _keyboard_type_for_value_text(value_text)
    if multiline:
        min_lines = 3
        if height is not None and float(height) >= 120.0:
            min_lines = 4
        decoration = (
            "InputDecoration("
            f"hintText: '{escaped_value}', "
            "border: InputBorder.none, "
            "contentPadding: EdgeInsets.fromLTRB(12.0, 12.0, 12.0, 12.0)"
            ")"
        )
        field = (
            f"TextField("
            f"maxLines: null, "
            f"minLines: {min_lines}, "
            f"textAlignVertical: TextAlignVertical.top, "
            f"style: {input_style}, "
            f"decoration: {decoration})"
        )
    else:
        decoration = (
            "InputDecoration("
            "border: InputBorder.none, "
            "contentPadding: EdgeInsets.symmetric(horizontal: 12.0)"
            ")"
        )
        field = _prefilled_input_field_expr(
            escaped_value=escaped_value,
            obscure="false",
            input_style=input_style,
            decoration=decoration,
            keyboard_type=keyboard_type,
            vertical_center=True,
        )
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    if (
        box_decoration is not None
        and width is not None
        and height is not None
        and float(width) > 0
        and float(height) > 0
    ):
        field = _compose_fixed_height_input_surface(
            field,
            width=float(width),
            height=float(height),
            box_decoration=box_decoration,
        )
    label = escape_dart_string(shell.accessibility_label or value_text or "Field")
    body = f"Semantics(label: '{label}', child: {field})"
    if flow_column_child:
        return body
    return _finalize_widget(
        shell,
        body,
        parent_type=parent_type,
    )


def build_decomposed_absolute_field_widgets(
    siblings: list[CleanDesignTreeNode],
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
) -> tuple[dict[str, str], set[str]]:
    """Build merged field widgets for painted absolute shells and omit their value text."""
    widgets_by_shell_id: dict[str, str] = {}
    omit_ids: set[str] = set()
    for child in siblings:
        if not layout_fact_painted_field_shell_container(child):
            continue
        value_node = find_field_shell_value_text(child, siblings)
        if value_node is None:
            continue
        widgets_by_shell_id[child.id] = render_decomposed_absolute_field(
            child,
            value_node,
            theme_variant=theme_variant,
            parent_type=parent_type,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        omit_ids.add(child.id)
        omit_ids.add(value_node.id)
    return widgets_by_shell_id, omit_ids

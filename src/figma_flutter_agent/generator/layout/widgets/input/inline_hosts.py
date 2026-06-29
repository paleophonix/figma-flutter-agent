"""Emit inline labeled input hosts and phone composite fields."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.form import wrap_material_input_child
from figma_flutter_agent.generator.layout.style import (
    box_decoration_expr,
    text_style_expr,
    text_widget_trailing_params,
)
from figma_flutter_agent.parser.interaction.inline_input_hosts import (
    coerce_inline_input_field_host,
    coerce_single_surface_input_field_host,
    layout_fact_inline_labeled_input_field_host,
    layout_fact_phone_composite_field_host,
    layout_fact_single_surface_input_field_column,
    phone_composite_prefix_node,
    phone_composite_value_node,
)
from figma_flutter_agent.parser.interaction.input_fields import input_surface_node
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..finalize import _finalize_widget
from .decoration import _stack_input_decoration
from .fields import (
    _compose_fixed_height_input_surface,
    _prefilled_input_field_expr,
    _render_flex_input_with_trailing_chrome,
    _render_stack_input,
)


def render_inline_labeled_input_field_host(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    uses_svg: bool,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Compile a labeled input component column into one bounded ``TextFormField``."""
    from figma_flutter_agent.parser.interaction.input_fields import input_trailing_chrome_nodes

    host = coerce_inline_input_field_host(node)
    trailing = input_trailing_chrome_nodes(host)
    if not trailing:
        surface = input_surface_node(host)
        if surface is not None:
            trailing = input_trailing_chrome_nodes(surface)
    if trailing:
        return _render_flex_input_with_trailing_chrome(
            host,
            trailing,
            theme_variant=theme_variant,
            parent_type=parent_type,
            uses_svg=uses_svg,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    return _render_stack_input(
        host,
        theme_variant=theme_variant,
        parent_type=parent_type,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        uses_svg=uses_svg,
    )


def render_phone_composite_field_host(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    uses_svg: bool,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Compile a phone composite column into prefix chrome plus an editable body field."""
    from figma_flutter_agent.generator.layout.widgets import render_node_body

    surface = next(
        child
        for child in node.children
        if phone_composite_value_node(child) is not None
        and phone_composite_prefix_node(child) is not None
    )
    label = next(child for child in node.children if child.id != surface.id)
    prefix = phone_composite_prefix_node(surface)
    value_node = phone_composite_value_node(surface)
    assert prefix is not None and value_node is not None
    width = surface.sizing.width
    height = surface.sizing.height
    prefix_emit = prefix
    prefix_updates: dict[str, object] = {}
    if height is not None and float(height) > 0:
        prefix_updates["sizing"] = prefix.sizing.model_copy(update={"height": float(height)})
    if prefix.style.border_color is not None or prefix.style.border_width is not None:
        prefix_updates["style"] = prefix.style.model_copy(
            update={"border_color": None, "border_width": None, "has_stroke": False},
        )
    if prefix_updates:
        prefix_emit = prefix.model_copy(update=prefix_updates)
    value_text = escape_dart_string((value_node.text or "").strip())
    box_decoration = box_decoration_expr(
        surface.style,
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
    decoration = _stack_input_decoration(
        surface,
        None,
        "",
        host_node=surface,
        field_height=height,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        surface_on_container=True,
        vertical_center=True,
    )
    field = _prefilled_input_field_expr(
        escaped_value=value_text,
        obscure="false",
        input_style=input_style,
        decoration=decoration,
        keyboard_type="TextInputType.phone",
        vertical_center=True,
    )
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    prefix_body = render_node_body(
        prefix_emit,
        uses_svg=uses_svg,
        parent_type=NodeType.ROW,
        parent_node=surface,
        theme_variant=theme_variant,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    prefix_zone = inline_custom_code_comment(
        custom_code_zone_id(prefix.id, "prefix-dropdown"),
    )
    outer_radius = float(surface.style.border_radius or 0.0)
    radius_lit = format_geometry_literal(outer_radius) if outer_radius > 0 else "10.0"
    prefix_width = prefix.sizing.width
    prefix_width_lit = (
        format_geometry_literal(float(prefix_width))
        if prefix_width is not None and float(prefix_width) > 0
        else "62.0"
    )
    prefix_height_lit = (
        format_geometry_literal(float(height))
        if height is not None and float(height) > 0
        else "46.0"
    )
    prefix_slot = (
        "Material("
        "color: Colors.transparent, "
        "child: InkWell("
        f"onTap: () {{ {prefix_zone} }}, "
        "child: ClipRRect("
        f"borderRadius: BorderRadius.horizontal(left: Radius.circular({radius_lit})), "
        f"child: SizedBox(width: {prefix_width_lit}, height: {prefix_height_lit}, "
        f"child: {prefix_body}"
        ")"
        ")"
        ")"
        ")"
    )
    row = (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [{prefix_slot}, Expanded(child: {field})]"
        ")"
    )
    if (
        box_decoration is not None
        and width is not None
        and height is not None
        and float(width) > 0
        and float(height) > 0
    ):
        row = _compose_fixed_height_input_surface(
            row,
            width=float(width),
            height=float(height),
            box_decoration=box_decoration,
        )
        if outer_radius > 0:
            row = (
                f"ClipRRect("
                f"borderRadius: BorderRadius.circular({radius_lit}), "
                f"child: {row}"
                ")"
            )
    external_label = None
    for child in label.children:
        if child.type == NodeType.TEXT and (child.text or "").strip():
            external_label = child
            break
    if external_label is None:
        for child in label.children:
            for grand in child.children:
                if grand.type == NodeType.TEXT and (grand.text or "").strip():
                    external_label = grand
                    break
    if external_label is not None:
        label_text = escape_dart_string((external_label.text or "").strip())
        style_expr = text_style_expr(
            external_label,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        trailing = text_widget_trailing_params(external_label.style, soft_wrap=False)
        label_widget = f"Text('{label_text}', style: {style_expr}, {trailing})"
        spacing = node.spacing or 0.0
        spacing_field = (
            f"spacing: {format_geometry_literal(spacing)}, " if spacing > 0 else ""
        )
        row = (
            f"Column(mainAxisSize: MainAxisSize.min, "
            f"crossAxisAlignment: CrossAxisAlignment.stretch, "
            f"{spacing_field}"
            f"children: [{label_widget}, {row}])"
        )
    return _finalize_widget(node, row, parent_type=parent_type)


def try_render_inline_input_field_host(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    parent_type: NodeType | None,
    uses_svg: bool,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Render inline input hosts when structural layout facts match."""
    if layout_fact_phone_composite_field_host(node):
        return render_phone_composite_field_host(
            node,
            theme_variant=theme_variant,
            parent_type=parent_type,
            uses_svg=uses_svg,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    if layout_fact_inline_labeled_input_field_host(node):
        return render_inline_labeled_input_field_host(
            node,
            theme_variant=theme_variant,
            parent_type=parent_type,
            uses_svg=uses_svg,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    if layout_fact_single_surface_input_field_column(node):
        from figma_flutter_agent.parser.interaction.input_fields import input_trailing_chrome_nodes

        host = coerce_single_surface_input_field_host(node)
        trailing = input_trailing_chrome_nodes(host)
        if trailing:
            return _render_flex_input_with_trailing_chrome(
                host,
                trailing,
                theme_variant=theme_variant,
                parent_type=parent_type,
                uses_svg=uses_svg,
                bundled_font_families=bundled_font_families,
                dart_weight_overrides_by_family=dart_weight_overrides_by_family,
                text_theme_slot_by_style_name=text_theme_slot_by_style_name,
                text_theme_size_slots=text_theme_size_slots,
            )
        return _render_stack_input(
            host,
            theme_variant=theme_variant,
            parent_type=parent_type,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
            uses_svg=uses_svg,
        )
    return None

"""Top-level input/textarea field widget emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.form import wrap_material_input_child
from figma_flutter_agent.generator.layout.style import (
    box_decoration_expr,
    text_style_expr,
    text_widget_trailing_params,
)
from figma_flutter_agent.parser.interaction import (
    input_external_label_node,
    input_flex_value_text,
    input_hint_implies_obscure_text,
    input_hint_node,
    input_hint_text,
    input_surface_node,
    input_trailing_chrome_implies_obscure_text,
    input_trailing_chrome_nodes,
    input_value_style_node,
    interaction_surface_node,
    layout_fact_password_field_stack,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..finalize import _finalize_widget
from ..shared import _node_layout_size
from .decoration import _input_text_style_expr, _stack_input_decoration
from .icons import _render_input_trailing_suffix_icon


def _input_obscure_flag(node: CleanDesignTreeNode, hint: str) -> str:
    """Return Dart bool literal for ``obscureText`` on flex/stack input hosts."""
    if (
        layout_fact_password_field_stack(node)
        or input_hint_implies_obscure_text(hint)
        or input_trailing_chrome_implies_obscure_text(node)
    ):
        return "true"
    for child in node.children:
        if child.type != NodeType.INPUT:
            continue
        if layout_fact_password_field_stack(child) or input_trailing_chrome_implies_obscure_text(
            child
        ):
            return "true"
    return "false"


def _input_surface_layout_size(
    surface: CleanDesignTreeNode | None,
    node: CleanDesignTreeNode,
) -> tuple[float | None, float | None]:
    """Return painted field width/height, not the outer label+field host bbox."""
    width, height = _node_layout_size(surface or node, node.stack_placement)
    if surface is not None:
        if surface.sizing.width is not None and surface.sizing.width > 0:
            width = surface.sizing.width
        if surface.sizing.height is not None and surface.sizing.height > 0:
            height = surface.sizing.height
    return width, height


def _compose_fixed_height_input_surface(
    inner: str,
    *,
    width: float,
    height: float,
    box_decoration: str,
) -> str:
    """Paint a fixed input shell and give the field tight vertical constraints."""
    width_lit = format_geometry_literal(width)
    height_lit = format_geometry_literal(height)
    return (
        f"Container("
        f"width: {width_lit}, height: {height_lit}, "
        f"decoration: {box_decoration}, "
        f"child: SizedBox("
        f"width: {width_lit}, height: {height_lit}, "
        f"child: {inner}"
        f")"
        f")"
    )


def _compose_external_label_input(
    node: CleanDesignTreeNode,
    field_widget: str,
    *,
    label_node: CleanDesignTreeNode,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Stack a field label above the control when Figma places it outside the surface."""
    label_text = escape_dart_string((label_node.text or "").strip())
    style_expr = text_style_expr(
        label_node,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    trailing = text_widget_trailing_params(label_node.style, soft_wrap=False)
    label_widget = f"Text('{label_text}', style: {style_expr}, {trailing})"
    spacing = node.spacing or 0.0
    spacing_field = f"spacing: {format_geometry_literal(spacing)}, " if spacing > 0 else ""
    return (
        f"Column(mainAxisSize: MainAxisSize.min, "
        f"crossAxisAlignment: CrossAxisAlignment.stretch, "
        f"{spacing_field}"
        f"children: [{label_widget}, {field_widget}])"
    )


def _prefilled_input_field_expr(
    *,
    escaped_value: str,
    obscure: str,
    input_style: str,
    decoration: str,
    keyboard_type: str | None = None,
    vertical_center: bool = False,
) -> str:
    """Emit a stateless prefilled input without per-build ``TextEditingController``."""
    keyboard = f"keyboardType: {keyboard_type}, " if keyboard_type else ""
    align = "textAlignVertical: TextAlignVertical.center, " if vertical_center else ""
    return (
        f"TextFormField("
        f"{align}"
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
    trailing_nodes: list[CleanDesignTreeNode] | None = None,
    uses_svg: bool = False,
) -> str:
    """Render a positioned ``TextField`` for classic absolute input groups."""
    surface = input_surface_node(node) or interaction_surface_node(node)
    hint_node = input_hint_node(node)
    hint = input_hint_text(node)
    external_label = input_external_label_node(node)
    width, height = _input_surface_layout_size(surface, node)
    field_height = surface.sizing.height if surface is not None else height
    vertical_center = field_height is not None and field_height > 0
    align_field = "textAlignVertical: TextAlignVertical.center, " if vertical_center else ""
    trailing = list(trailing_nodes or input_trailing_chrome_nodes(node))
    if not trailing:
        for child in node.children:
            if child.type == NodeType.INPUT:
                trailing = input_trailing_chrome_nodes(child)
                if trailing:
                    break
    suffix_icon = None
    if trailing:
        suffix_icon = _render_input_trailing_suffix_icon(
            trailing[0],
            host_node=node,
            uses_svg=uses_svg,
            theme_variant=theme_variant,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
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
        surface_on_container=surface is not None and surface.style.background_color is not None,
        suffix_icon=suffix_icon,
        vertical_center=vertical_center,
    )
    obscure = _input_obscure_flag(node, hint)
    input_style = _input_text_style_expr(
        node,
        hint_node=hint_node,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    from figma_flutter_agent.parser.interaction.forms import layout_fact_tall_multiline_input_shell

    multiline_field = layout_fact_tall_multiline_input_shell(node, field_height=field_height)
    multiline_attrs = "maxLines: null, minLines: 3, " if multiline_field else ""
    value_node = input_value_style_node(node)
    if value_node is None:
        for child in node.children:
            if child.type == NodeType.INPUT:
                value_node = input_value_style_node(child)
                if value_node is not None:
                    break
    value_text = (value_node.text or "").strip() if value_node is not None else None
    if not value_text:
        value_text = input_flex_value_text(node)
        if value_text is None:
            for child in node.children:
                if child.type == NodeType.INPUT:
                    value_text = input_flex_value_text(child)
                    if value_text is not None:
                        break
    if value_text:
        escaped_value = escape_dart_string(value_text)
        field = _prefilled_input_field_expr(
            escaped_value=escaped_value,
            obscure=obscure,
            input_style=input_style,
            decoration=decoration,
            vertical_center=vertical_center,
        )
    else:
        field = (
            f"TextField({align_field}{multiline_attrs}obscureText: {obscure}, "
            f"style: {input_style}, decoration: {decoration})"
        )
    field = wrap_material_input_child(field, theme_variant=theme_variant)
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
            if vertical_center:
                field = _compose_fixed_height_input_surface(
                    field,
                    width=float(width),
                    height=float(height),
                    box_decoration=box_decoration,
                )
            else:
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
    elif height is not None and height > 0 and external_label is None:
        field = f"SizedBox(height: {height}, child: {field})"
    semantic_label = (
        external_label.text
        if external_label is not None and external_label.text
        else node.accessibility_label or hint
    )
    label = escape_dart_string(semantic_label)
    field = f"Semantics(label: '{label}', child: {field})"
    if external_label is not None:
        field = _compose_external_label_input(
            node,
            field,
            label_node=external_label,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
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
    from figma_flutter_agent.generator.layout.common import escape_figma_text_literal
    from figma_flutter_agent.generator.layout.scroll import padding_edge_insets
    from figma_flutter_agent.parser.interaction import textarea_hint_node, textarea_surface_node

    hint_node = textarea_hint_node(node)
    surface = textarea_surface_node(node)
    hint_raw = (
        (hint_node.text if hint_node is not None else None) or node.accessibility_label or "Comment"
    )
    hint = (
        escape_figma_text_literal(hint_node)
        if hint_node is not None
        else escape_dart_string(hint_raw)
    )
    hint_style = (
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
    input_style = "Theme.of(context).textTheme.bodyMedium"
    height = node.sizing.height
    min_lines = 3
    if height is not None and float(height) >= 120.0:
        min_lines = 4
    content_padding = (
        padding_edge_insets(node) or "const EdgeInsets.fromLTRB(16.0, 12.0, 16.0, 12.0)"
    )
    field = (
        f"TextField("
        f"maxLines: null, "
        f"minLines: {min_lines}, "
        f"textAlignVertical: TextAlignVertical.top, "
        f"style: {input_style}, "
        f"decoration: InputDecoration("
        f"hintText: '{hint}', "
        f"hintStyle: {hint_style}, "
        f"border: InputBorder.none, "
        f"contentPadding: {content_padding}"
        f"))"
    )
    field = wrap_material_input_child(field, theme_variant=theme_variant)
    box_decoration = None
    if surface is not None:
        box_decoration = box_decoration_expr(
            surface.style,
            width=surface.sizing.width,
            height=surface.sizing.height,
        )
    if box_decoration is None:
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
    external_label = input_external_label_node(node)
    value_text = input_flex_value_text(node)
    width, height = _input_surface_layout_size(surface, node)

    suffix_icon = _render_input_trailing_suffix_icon(
        trailing[0],
        host_node=node,
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
    align_field = "textAlignVertical: TextAlignVertical.center, " if vertical_center else ""
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
        surface_on_container=surface is not None and surface.style.background_color is not None,
        suffix_icon=suffix_icon,
        vertical_center=vertical_center,
    )
    obscure = _input_obscure_flag(node, hint)
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
            vertical_center=vertical_center,
        )
    else:
        field = (
            f"TextField({align_field}obscureText: {obscure}, "
            f"style: {input_style}, decoration: {decoration})"
        )
    if height is not None and height > 0 and external_label is None and not vertical_center:
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
        if vertical_center:
            composed = _compose_fixed_height_input_surface(
                field,
                width=float(width),
                height=float(height),
                box_decoration=box_decoration,
            )
        else:
            composed = (
                f"Container(width: {width}, height: {height}, "
                f"decoration: {box_decoration}, child: {field})"
            )
    else:
        composed = field
    if external_label is not None:
        composed = _compose_external_label_input(
            node,
            composed,
            label_node=external_label,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    semantic_label = (
        external_label.text
        if external_label is not None and external_label.text
        else node.accessibility_label or input_hint_text(node)
    )
    label = escape_dart_string(semantic_label)
    return _finalize_widget(
        node,
        f"Semantics(label: '{label}', child: {composed})",
        parent_type=parent_type,
    )

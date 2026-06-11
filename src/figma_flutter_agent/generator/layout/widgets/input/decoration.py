"""InputDecoration construction helpers for input field widgets."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.style import (
    dart_color_expr,
    text_style_expr,
)
from figma_flutter_agent.parser.interaction import (
    input_value_style_node,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode


def _input_style_line_box_height(
    style_ref: CleanDesignTreeNode | None,
    *,
    fallback: float = 14.0,
) -> float:
    """Return the Flutter line-box height used to center copy inside fixed inputs."""
    if style_ref is None:
        return fallback
    metrics = style_ref.text_metrics_frame
    if metrics is not None and metrics.line_height_px is not None and metrics.line_height_px > 0:
        return float(metrics.line_height_px)
    font_size = style_ref.style.font_size if style_ref.style.font_size is not None else fallback
    glyph_height = style_ref.style.glyph_height
    if glyph_height is not None and glyph_height > 0:
        return float(glyph_height)
    line_height = style_ref.style.line_height
    if line_height is not None and line_height > 0:
        return float(font_size) * float(line_height)
    return float(font_size)


def _flex_input_content_padding(
    node: CleanDesignTreeNode,
    hint_node: CleanDesignTreeNode | None,
    field_height: float | None,
) -> str | None:
    """Derive ``InputDecoration.contentPadding`` for flex-hug ``INPUT`` frames."""
    if field_height is None or field_height <= 0:
        return None
    pad = node.padding
    left = pad.left if pad is not None and pad.left is not None else 16.0
    right = pad.right if pad is not None and pad.right is not None else 16.0
    if pad is not None and ((pad.top or 0) > 0 or (pad.bottom or 0) > 0):
        top = pad.top or 0.0
        bottom = pad.bottom or 0.0
        return (
            f"contentPadding: EdgeInsets.fromLTRB(" f"{left}, {top}, {right}, {bottom})"
        )
    value_node = input_value_style_node(node)
    style_ref = value_node or hint_node
    text_height = _input_style_line_box_height(style_ref)
    top = max(0.0, (float(field_height) - float(text_height)) / 2.0)
    bottom = max(0.0, float(field_height) - top - float(text_height))
    return f"contentPadding: EdgeInsets.fromLTRB({left}, {top}, {right}, {bottom})"


def _optical_single_line_input_content_padding(
    node: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    field_height: float | None,
) -> str | None:
    """Symmetric vertical padding from cap-height centering inside a fixed input."""
    if node is None or field_height is None or field_height <= 0:
        return None
    pad = node.padding
    has_explicit_padding = pad is not None and any(
        value not in (None, 0, 0.0)
        for value in (pad.top, pad.bottom, pad.left, pad.right)
    )
    if (
        not has_explicit_padding
        and hint_node is not None
        and hint_node.stack_placement is not None
    ):
        return None
    left = 16.0
    right = 16.0
    if node.padding is not None:
        if node.padding.left is not None:
            left = float(node.padding.left)
        if node.padding.right is not None:
            right = float(node.padding.right)
    value_node = input_value_style_node(node)
    style_ref = value_node or hint_node
    line_box = _input_style_line_box_height(style_ref)
    vertical = max(0.0, (float(field_height) - line_box) / 2.0)
    pad = node.padding
    if (
        pad is not None
        and pad.top is not None
        and pad.bottom is not None
        and abs(float(pad.top) - float(pad.bottom)) <= 1.0
    ):
        vertical = max(vertical, float(pad.top))
    left_lit = format_geometry_literal(left)
    right_lit = format_geometry_literal(right)
    top_lit = format_geometry_literal(vertical)
    return f"contentPadding: EdgeInsets.fromLTRB({left_lit}, {top_lit}, {right_lit}, {top_lit})"


def _input_content_padding(
    surface: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    field_height: float | None,
) -> str | None:
    """Derive ``InputDecoration.contentPadding`` from Figma placeholder placement."""
    if (
        surface is None
        or hint_node is None
        or field_height is None
        or field_height <= 0
    ):
        return None
    placement = hint_node.stack_placement
    if placement is None:
        return None
    left = placement.left if placement.left is not None else 20.0
    text_height = hint_node.style.glyph_height or placement.height
    font_size = hint_node.style.font_size or 16.0
    line_height = hint_node.style.line_height or 1.0
    computed_height = font_size * line_height
    if text_height is None or text_height <= 0:
        text_height = computed_height
    figma_top = (placement.top if placement.top is not None else 0.0) + (
        hint_node.style.glyph_top_offset or 0.0
    )
    centered_top = max(0.0, (field_height - text_height) / 2.0)
    top = figma_top if figma_top >= centered_top - 1.0 else centered_top
    bottom = max(0.0, field_height - top - text_height)
    right = left
    return f"contentPadding: EdgeInsets.fromLTRB({left}, {top}, {right}, {bottom})"


def _planner_input_content_padding(node: CleanDesignTreeNode) -> str | None:
    """Use geometry-planner INPUT padding channel when present."""
    metrics = node.text_metrics_frame
    if metrics is None or metrics.input_padding_top is None:
        return None
    pad = node.padding
    left = pad.left if pad is not None and pad.left is not None else 16.0
    right = pad.right if pad is not None and pad.right is not None else left
    top = format_geometry_literal(metrics.input_padding_top)
    bottom = format_geometry_literal(metrics.input_padding_bottom or 0.0)
    left_lit = format_geometry_literal(left)
    right_lit = format_geometry_literal(right)
    return f"contentPadding: EdgeInsets.fromLTRB({left_lit}, {top}, {right_lit}, {bottom})"


def _stack_input_decoration(
    surface: CleanDesignTreeNode | None,
    hint_node: CleanDesignTreeNode | None,
    hint: str,
    *,
    host_node: CleanDesignTreeNode | None = None,
    field_height: float | None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    surface_on_container: bool = False,
    suffix_icon: str | None = None,
    vertical_center: bool = False,
) -> str:
    """Build ``InputDecoration`` for heuristic input stacks."""
    hint_text = escape_dart_string(hint)
    fields = [f"hintText: '{hint_text}'"]
    if hint_node is not None:
        fields.append(
            f"hintStyle: {text_style_expr(hint_node, bundled_font_families=bundled_font_families, dart_weight_overrides_by_family=dart_weight_overrides_by_family, text_theme_slot_by_style_name=text_theme_slot_by_style_name, text_theme_size_slots=text_theme_size_slots)}"
        )
    if surface_on_container:
        padding = None
        if vertical_center:
            padding = _optical_single_line_input_content_padding(
                host_node,
                hint_node,
                field_height,
            )
        if padding is None and host_node is not None and host_node.layout_slot is not None:
            padding = _planner_input_content_padding(host_node)
        if padding is None:
            padding = _input_content_padding(surface, hint_node, field_height)
        if padding is None and host_node is not None:
            padding = _flex_input_content_padding(host_node, hint_node, field_height)
        if padding is not None:
            fields.append(padding)
        else:
            left = 20.0
            if (
                hint_node is not None
                and hint_node.stack_placement is not None
                and hint_node.stack_placement.left is not None
            ):
                left = hint_node.stack_placement.left
            fields.append(
                f"contentPadding: EdgeInsets.symmetric(horizontal: {left}, vertical: 0)"
            )
        fields.append("border: InputBorder.none")
        fields.append("enabledBorder: InputBorder.none")
        fields.append("focusedBorder: InputBorder.none")
        fields.append("disabledBorder: InputBorder.none")
        fields.append("errorBorder: InputBorder.none")
        fields.append("focusedErrorBorder: InputBorder.none")
    else:
        padding = _input_content_padding(surface, hint_node, field_height)
        if padding is not None:
            fields.append(padding)
        if surface is not None and surface.style.background_color:
            fields.append("filled: true")
            fields.append(f"fillColor: {dart_color_expr(surface.style)}")
        radius = surface.style.border_radius if surface is not None else None
        if radius is not None:
            fields.append(
                "border: OutlineInputBorder("
                f"borderRadius: BorderRadius.circular({radius}), "
                "borderSide: BorderSide.none"
                ")"
            )
            fields.append(
                "enabledBorder: OutlineInputBorder("
                f"borderRadius: BorderRadius.circular({radius}), "
                "borderSide: BorderSide.none"
                ")"
            )
    if suffix_icon is not None:
        fields.append(f"suffixIcon: {suffix_icon}")
    return f"InputDecoration({', '.join(fields)})"


def _input_text_style_expr(
    node: CleanDesignTreeNode,
    *,
    hint_node: CleanDesignTreeNode | None,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Prefer prefilled value typography over the field label for ``TextField.style``."""
    value_node = input_value_style_node(node)
    style_node = value_node or hint_node
    if style_node is not None:
        return text_style_expr(
            style_node,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
    return "Theme.of(context).textTheme.bodyMedium"

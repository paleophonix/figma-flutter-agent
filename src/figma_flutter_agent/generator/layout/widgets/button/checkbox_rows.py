"""Consent-checkbox and checkbox-label row emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.emit_text_span import (
    emit_text_rich,
    emit_text_span_children_from_node,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.form import render_checkbox
from figma_flutter_agent.generator.layout.style import (
    text_align_expr,
    text_style_expr,
    text_widget_trailing_params,
)
from figma_flutter_agent.parser.interaction import is_link_text, layout_fact_checkbox_control
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

from ..layout import _flex_spacing_field


def _wrap_primary_cta_text(widget: str, *, node_id: str) -> str:
    """Wrap primary CTA label text with a custom-code interaction slot."""
    from figma_flutter_agent.generator.custom_code_zones import (
        custom_code_zone_id,
        inline_custom_code_comment,
    )

    zone = inline_custom_code_comment(custom_code_zone_id(node_id, "button-action"))
    return (
        "MouseRegion("
        "cursor: SystemMouseCursors.click, "
        f"child: GestureDetector(onTap: () {{ {zone} }}, "
        f"behavior: HitTestBehavior.opaque, child: {widget})"
        ")"
    )


def _wrap_link_text(widget: str) -> str:
    """Wrap a text widget with a tappable link affordance."""
    return (
        "MouseRegion("
        "cursor: SystemMouseCursors.click, "
        f"child: GestureDetector(onTap: () {{}}, behavior: HitTestBehavior.opaque, child: {widget})"
        ")"
    )


def _is_consent_checkbox_row_stack(node: CleanDesignTreeNode) -> bool:
    """Synthetic row from ``reconcile_consent_checkbox_rows_in_tree``."""
    return node.type == NodeType.STACK and (
        node.name == "ConsentRow" or str(node.id).endswith("-consent-row")
    )


def _wrap_compact_checkbox_control(widget: str, *, width: float, height: float) -> str:
    """Center a compact checkbox inside its Figma square without tap-target drift."""
    width_lit = format_geometry_literal(width)
    height_lit = format_geometry_literal(height)
    return f"SizedBox(width: {width_lit}, height: {height_lit}, child: Center(child: {widget}))"


def _emit_compact_inline_label_text(
    label_child: CleanDesignTreeNode,
    *,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str:
    """Emit single-line label copy optically centered beside compact controls."""
    align = text_align_expr(label_child.style)
    align_suffix = f", textAlign: {align}" if align else ""
    if label_child.text_spans:
        span_parts = emit_text_span_children_from_node(
            label_child,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        return emit_text_rich(span_parts, text_align_suffix=align_suffix)
    text = escape_dart_string(label_child.text or label_child.name)
    style_expr = text_style_expr(
        label_child,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        omit_line_height=True,
    )
    trailing = text_widget_trailing_params(
        label_child.style,
        text_align_suffix=align_suffix,
        omit_strut=True,
        optical_center=True,
    )
    return f"Text('{text}', style: {style_expr}, {trailing})"


def _try_render_consent_checkbox_row(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Render privacy copy and checkbox as one tappable row."""
    if not _is_consent_checkbox_row_stack(node):
        return None
    checkbox_child = next(
        (child for child in node.children if layout_fact_checkbox_control(child)),
        None,
    )
    label_child = next(
        (child for child in node.children if child.type == NodeType.TEXT),
        None,
    )
    if checkbox_child is None or label_child is None:
        return None
    text_widget = _emit_compact_inline_label_text(
        label_child,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if is_link_text(label_child.text):
        text_widget = _wrap_link_text(text_widget)
    checkbox_widget = render_checkbox(checkbox_child, theme_variant=theme_variant)
    width = checkbox_child.sizing.width
    height = checkbox_child.sizing.height
    if width is not None and height is not None and width > 0 and height > 0:
        checkbox_widget = _wrap_compact_checkbox_control(
            checkbox_widget,
            width=float(width),
            height=float(height),
        )
    return (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [Expanded(child: {text_widget}), {checkbox_widget}]"
        ")"
    )


def _try_render_checkbox_label_row(
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Render a checkbox host beside label copy with centered cross-axis alignment."""
    from figma_flutter_agent.parser.interaction import (
        checkbox_label_text_host,
        compact_checkbox_leaf,
        row_hosts_checkbox_label_pair,
    )

    if not row_hosts_checkbox_label_pair(node):
        return None
    checkbox_host = next(
        child for child in node.children if compact_checkbox_leaf(child) is not None
    )
    label_child = next(
        child for child in node.children if checkbox_label_text_host(child) is not None
    )
    label_leaf = checkbox_label_text_host(label_child)
    if label_leaf is None:
        return None
    label_child = label_leaf
    checkbox_node = compact_checkbox_leaf(checkbox_host)
    if checkbox_node is None:
        return None
    text_widget = _emit_compact_inline_label_text(
        label_child,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if is_link_text(label_child.text):
        text_widget = _wrap_link_text(text_widget)
    checkbox_widget = render_checkbox(checkbox_node, theme_variant=theme_variant)
    width = checkbox_node.sizing.width
    height = checkbox_node.sizing.height
    if width is not None and height is not None and width > 0 and height > 0:
        checkbox_widget = _wrap_compact_checkbox_control(
            checkbox_widget,
            width=float(width),
            height=float(height),
        )
    spacing_field = _flex_spacing_field(node)
    return (
        "Row("
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"{spacing_field}"
        f"children: [{checkbox_widget}, Expanded(child: {text_widget})]"
        ")"
    )


__all__ = [
    "_emit_compact_inline_label_text",
    "_is_consent_checkbox_row_stack",
    "_try_render_checkbox_label_row",
    "_try_render_consent_checkbox_row",
    "_wrap_compact_checkbox_control",
    "_wrap_link_text",
    "_wrap_primary_cta_text",
]

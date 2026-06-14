"""Deterministic emit helpers for Figma Tag option chips."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.cupertino import wrap_button_stack
from figma_flutter_agent.generator.layout.scroll import padding_edge_insets
from figma_flutter_agent.generator.layout.style import dart_color_expr
from figma_flutter_agent.parser.interaction.chip_variant import chip_component_selected
from figma_flutter_agent.parser.interaction.shared import _local_nodes
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_TAG_DEFAULT_SURFACE = "0xFFEAF2FF"
_TAG_SELECTED_SURFACE = "0xFF006FFD"
_TAG_UNSELECTED_TEXT = "0xFF006FFD"
_TAG_SELECTED_TEXT = "0xFFFFFFFF"


def _tag_option_unselected_text_color_expr(node: CleanDesignTreeNode) -> str:
    for item in _local_nodes(node, 4):
        if item.type == NodeType.TEXT and item.style.text_color:
            return dart_color_expr(item.style, fallback=_TAG_UNSELECTED_TEXT)
    return f"Color({_TAG_UNSELECTED_TEXT})"


def _tag_option_chip_background_exprs(node: CleanDesignTreeNode) -> tuple[str, str]:
    """Return stable ``(unselected_bg, selected_bg)`` for chip widget ternaries."""
    selected_bg = f"Color({_TAG_SELECTED_SURFACE})"
    if chip_component_selected(node):
        unselected_bg = f"Color({_TAG_DEFAULT_SURFACE})"
    else:
        unselected_bg = dart_color_expr(node.style, fallback=_TAG_DEFAULT_SURFACE)
    return unselected_bg, selected_bg


def render_tag_option_chip_body(
    node: CleanDesignTreeNode,
    *,
    label_expr: str = "label",
    is_selected_expr: str = "isSelected",
) -> str:
    """Emit a compact Tag option chip without ``FittedBox`` width hacks."""
    unselected_bg, selected_bg = _tag_option_chip_background_exprs(node)
    unselected_fg = _tag_option_unselected_text_color_expr(node)
    selected_fg = f"Color({_TAG_SELECTED_TEXT})"
    radius = node.style.border_radius or 12.0
    radius_lit = format_geometry_literal(radius)
    padding = padding_edge_insets(node) or "const EdgeInsets.fromLTRB(8.0, 6.0, 8.0, 6.0)"
    height = node.sizing.height
    height_lit = (
        format_geometry_literal(float(height))
        if height is not None and float(height) > 0
        else "24.0"
    )
    return (
        f"SizedBox("
        f"height: {height_lit}, "
        f"child: Container("
        f"decoration: BoxDecoration("
        f"color: {is_selected_expr} ? {selected_bg} : {unselected_bg}, "
        f"borderRadius: BorderRadius.circular({radius_lit})"
        f"), "
        f"padding: {padding}, "
        f"child: Center("
        f"child: Text("
        f"{label_expr}, "
        f"maxLines: 1, "
        f"softWrap: false, "
        f"overflow: TextOverflow.visible, "
        f"style: Theme.of(context).textTheme.bodyMedium?.copyWith("
        f"color: {is_selected_expr} ? {selected_fg} : {unselected_fg}, "
        f"fontSize: 12.0, "
        f"fontWeight: FontWeight.w600, "
        f"letterSpacing: 0.5"
        f"), "
        f"textScaler: textScaler, "
        f"strutStyle: const StrutStyle(fontSize: 12, height: 1.21, forceStrutHeight: true), "
        f"textAlign: TextAlign.center"
        f")))))"
    )


def wrap_tag_option_chip_interactive(
    body: str,
    node: CleanDesignTreeNode,
    *,
    theme_variant: str,
    label_expr: str = "label",
    is_selected_expr: str = "isSelected",
) -> str:
    """Wrap a tag option chip with tap target and accessibility semantics."""
    radius = node.style.border_radius or 12.0
    wrapped = wrap_button_stack(
        body,
        theme_variant=theme_variant,
        border_radius=radius,
        ink_fill_color=None,
        node_id=node.id,
        tap_role="chip-choice",
    )
    return (
        f"Semantics("
        f"button: true, "
        f"selected: {is_selected_expr}, "
        f"label: {label_expr}, "
        f"child: {wrapped}"
        f")"
    )


def wrap_tag_option_chip_reference(widget_expr: str, node: CleanDesignTreeNode) -> str:
    """Preserve per-instance chip width at call sites."""
    from figma_flutter_agent.parser.interaction.chip_variant import is_tag_component_chip_row

    width = node.sizing.width
    if is_tag_component_chip_row(node) and width is not None and float(width) > 0:
        width_lit = format_geometry_literal(float(width))
        return f"SizedBox(width: {width_lit}, child: {widget_expr})"
    return widget_expr

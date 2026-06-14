"""Deterministic emit helpers for Figma Tag option chips."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.cupertino import wrap_button_stack
from figma_flutter_agent.generator.layout.scroll import padding_edge_insets
from figma_flutter_agent.generator.layout.style.colors import dart_color_expr
from figma_flutter_agent.generator.layout.style.facts import label_color_on_surface_expr
from figma_flutter_agent.generator.layout.style.text_helpers import (
    _flutter_font_weight_expr,
    strut_style_expr,
)
from figma_flutter_agent.parser.interaction.chip_variant import (
    chip_cluster_style_refs,
    chip_component_label_font_size,
    chip_component_label_text_node,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

_SURFACE_FALLBACK = "Theme.of(context).colorScheme.surfaceContainerHighest"


def _chip_label_foreground_expr(chip_row: CleanDesignTreeNode) -> str:
    """Resolve chip label color from nested TEXT and row surface facts."""
    text_node = chip_component_label_text_node(chip_row)
    if text_node is not None:
        return label_color_on_surface_expr(
            text_node.style,
            surface_color=chip_row.style.background_color,
        )
    from figma_flutter_agent.generator.layout.style.colors import is_dark_fill_color

    on_dark = is_dark_fill_color(chip_row.style.background_color)
    return (
        "Theme.of(context).colorScheme.onPrimary"
        if on_dark
        else "Theme.of(context).colorScheme.onSurface"
    )


def _chip_surface_bg_expr(chip_row: CleanDesignTreeNode) -> str:
    """Return a Dart background expression from the chip row surface style."""
    return dart_color_expr(chip_row.style, fallback=_SURFACE_FALLBACK)


def _tag_option_chip_palette(
    representative: CleanDesignTreeNode,
    *,
    clean_trees: list[CleanDesignTreeNode] | None,
) -> tuple[str, str, str, str]:
    """Return ``(unselected_bg, selected_bg, unselected_fg, selected_fg)`` Dart exprs."""
    cluster_id = representative.cluster_id
    if cluster_id and clean_trees:
        unref, selref = chip_cluster_style_refs(clean_trees, cluster_id, representative)
    else:
        from figma_flutter_agent.parser.interaction.chip_variant import chip_component_selected

        unref = representative if not chip_component_selected(representative) else None
        selref = representative if chip_component_selected(representative) else None
    unselected_row = unref or representative
    selected_row = selref or representative
    return (
        _chip_surface_bg_expr(unselected_row),
        _chip_surface_bg_expr(selected_row),
        _chip_label_foreground_expr(unselected_row),
        _chip_label_foreground_expr(selected_row),
    )


def _chip_label_text_style_fields(chip_row: CleanDesignTreeNode) -> list[str]:
    """Build inline ``TextStyle`` fields from the chip label TEXT node."""
    text_node = chip_component_label_text_node(chip_row)
    style_source = text_node.style if text_node is not None else chip_row.style
    parts: list[str] = []
    font_size = chip_component_label_font_size(chip_row)
    if font_size is not None:
        parts.append(f"fontSize: {format_geometry_literal(font_size)}")
    weight_expr = _flutter_font_weight_expr(style_source)
    if weight_expr is not None:
        parts.append(f"fontWeight: {weight_expr}")
    if style_source.letter_spacing is not None:
        spacing = float(style_source.letter_spacing)
        if font_size is not None and font_size > 0:
            spacing = min(spacing, float(font_size) * 0.12)
        parts.append(f"letterSpacing: {format_micro_style_literal(spacing)}")
    return parts


def _chip_label_strut_suffix(chip_row: CleanDesignTreeNode) -> str:
    """Return optional ``strutStyle`` suffix for chip label ``Text``."""
    text_node = chip_component_label_text_node(chip_row)
    if text_node is None:
        return ""
    strut = strut_style_expr(text_node.style)
    if strut is not None:
        return f", strutStyle: {strut}"
    metrics = text_node.text_metrics_frame
    font_size = chip_component_label_font_size(chip_row)
    if metrics is not None and metrics.strut_height_ratio is not None and font_size is not None:
        ratio_lit = format_micro_style_literal(float(metrics.strut_height_ratio))
        size_lit = format_geometry_literal(font_size)
        return (
            f", strutStyle: StrutStyle(fontSize: {size_lit}, "
            f"height: {ratio_lit}, forceStrutHeight: true)"
        )
    return ""


def render_tag_option_chip_body(
    node: CleanDesignTreeNode,
    *,
    clean_trees: list[CleanDesignTreeNode] | None = None,
    label_expr: str = "label",
    is_selected_expr: str = "isSelected",
) -> str:
    """Emit a compact Tag option chip without ``FittedBox`` width hacks."""
    unselected_bg, selected_bg, unselected_fg, selected_fg = _tag_option_chip_palette(
        node,
        clean_trees=clean_trees,
    )
    typo_ref = node
    cluster_id = node.cluster_id
    if cluster_id and clean_trees:
        unref, _ = chip_cluster_style_refs(clean_trees, cluster_id, node)
        if unref is not None:
            typo_ref = unref
    style_parts = [f"color: {is_selected_expr} ? {selected_fg} : {unselected_fg}"]
    style_parts.extend(_chip_label_text_style_fields(typo_ref))
    strut_suffix = _chip_label_strut_suffix(typo_ref)
    radius_lit = (
        format_geometry_literal(float(node.style.border_radius))
        if node.style.border_radius is not None
        else "Theme.of(context).extension<AppRadiusExtension>()?.md ?? 12.0"
    )
    padding = padding_edge_insets(node)
    if padding is None:
        padding = "Theme.of(context).extension<AppEdgeInsetsExtension>()?.chip ?? const EdgeInsets.symmetric(horizontal: 8.0, vertical: 6.0)"
    height = node.sizing.height
    height_lit = (
        format_geometry_literal(float(height))
        if height is not None and float(height) > 0
        else "Theme.of(context).extension<AppLayoutExtension>()?.chipHeight ?? 24.0"
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
        f"style: TextStyle({', '.join(style_parts)}), "
        f"textScaler: textScaler"
        f"{strut_suffix}, "
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

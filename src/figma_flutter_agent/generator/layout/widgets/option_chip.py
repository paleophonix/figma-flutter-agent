"""Deterministic emit helpers for Figma Tag option chips."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.cupertino import wrap_button_stack
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    layout_fact_stack_circular_option_glyph_host,
)
from figma_flutter_agent.generator.layout.scroll import padding_edge_insets
from figma_flutter_agent.generator.layout.style import text_style_expr
from figma_flutter_agent.generator.layout.style.colors import dart_color_expr
from figma_flutter_agent.generator.layout.style.facts import label_color_on_surface_expr
from figma_flutter_agent.generator.layout.style.text_helpers import (
    _flutter_font_weight_expr,
    strut_style_expr,
)
from figma_flutter_agent.parser.interaction.chip_variant import (
    chip_cluster_style_refs,
    chip_component_display_label,
    chip_component_label_font_size,
    chip_component_label_text_node,
    is_tag_component_chip_row,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, WidgetIrKind, WidgetIrNode

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


def _circular_chip_paint_surface(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    """Return the painted circular chip surface inside a compact option stack."""
    for child in node.children:
        if child.type == NodeType.CONTAINER and (
            child.style.background_color is not None or child.style.border_radius is not None
        ):
            return child
    return node


def _emit_circular_chip_choice_body(
    node: CleanDesignTreeNode,
    *,
    label: str,
    ctx: IrEmitContext,
) -> str:
    """Emit a square option chip stack with centered static label text."""
    text_node = chip_component_label_text_node(node)
    surface = _circular_chip_paint_surface(node)
    bg_expr = dart_color_expr(surface.style, fallback=_SURFACE_FALLBACK)
    radius_lit = (
        format_geometry_literal(float(surface.style.border_radius))
        if surface.style.border_radius is not None
        else "24.0"
    )
    width = node.sizing.width
    height = node.sizing.height
    width_lit = (
        format_geometry_literal(float(width)) if width is not None and float(width) > 0 else "48.0"
    )
    height_lit = (
        format_geometry_literal(float(height))
        if height is not None and float(height) > 0
        else width_lit
    )
    label_lit = f"'{escape_dart_string(label)}'"
    if text_node is not None:
        fg_expr = label_color_on_surface_expr(
            text_node.style,
            surface_color=surface.style.background_color,
        )
        style_expr = text_style_expr(
            text_node,
            bundled_font_families=ctx.bundled_font_families,
            dart_weight_overrides_by_family=ctx.dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=ctx.text_theme_slot_by_style_name,
            text_theme_size_slots=ctx.text_theme_size_slots,
        )
        text_widget = (
            f"Text({label_lit}, style: {style_expr}.copyWith(color: {fg_expr}), "
            "textScaler: textScaler, textAlign: TextAlign.center, maxLines: 1, softWrap: false)"
        )
    else:
        text_widget = (
            f"Text({label_lit}, style: Theme.of(context).textTheme.bodyMedium, "
            "textScaler: textScaler, textAlign: TextAlign.center, maxLines: 1, softWrap: false)"
        )
    return (
        "Stack("
        "clipBehavior: Clip.none, "
        "children: ["
        f"Container("
        f"width: {width_lit}, "
        f"height: {height_lit}, "
        f"decoration: BoxDecoration(color: {bg_expr}, "
        f"borderRadius: BorderRadius.circular({radius_lit}))"
        f"), "
        f"Center(child: {text_widget})"
        "]"
        ")"
    )


def emit_chip_choice_layout(
    ir: WidgetIrNode,
    *,
    clean: CleanDesignTreeNode,
    ctx: IrEmitContext,
) -> str:
    """Emit interactive ``chip_choice`` layout regardless of semantic report_only gate."""
    is_selected_expr = "true" if ir.is_selected else "false"
    if is_tag_component_chip_row(clean):
        label = chip_component_display_label(clean)
        label_lit = f"'{escape_dart_string(label)}'"
        body = render_tag_option_chip_body(
            clean,
            label_expr=label_lit,
            is_selected_expr=is_selected_expr,
        )
    elif layout_fact_stack_circular_option_glyph_host(clean):
        label = (chip_component_label_text_node(clean) or clean).text or ""
        label = label.strip() or chip_component_display_label(clean)
        body = _emit_circular_chip_choice_body(clean, label=label, ctx=ctx)
        label_lit = f"'{escape_dart_string(label)}'"
    else:
        label = chip_component_display_label(clean)
        label_lit = f"'{escape_dart_string(label)}'"
        body = render_tag_option_chip_body(
            clean,
            label_expr=label_lit,
            is_selected_expr=is_selected_expr,
        )
    radius = clean.style.border_radius
    surface = _circular_chip_paint_surface(clean)
    if radius is None and surface.style.border_radius is not None:
        radius = surface.style.border_radius
    wrapped = wrap_tag_option_chip_interactive(
        body,
        clean,
        theme_variant=ctx.theme_variant,
        label_expr=label_lit,
        is_selected_expr=is_selected_expr,
    )
    return wrap_tag_option_chip_reference(wrapped, clean)


def try_emit_chip_choice_layout_for_node(
    node: CleanDesignTreeNode,
    ctx: IrEmitContext | object,
    *,
    ir_by_id: dict[str, WidgetIrNode] | None = None,
) -> str | None:
    """Emit interactive chip_choice in deterministic layout when IR or structure matches."""
    from figma_flutter_agent.generator.layout.widgets.emit.context import LayoutRenderContext
    from figma_flutter_agent.parser.interaction.chip_variant import (
        chip_component_selected,
        is_tag_component_chip_row,
    )

    resolved_ir_by_id = ir_by_id
    if resolved_ir_by_id is None and isinstance(ctx, LayoutRenderContext):
        resolved_ir_by_id = ctx.ir_by_id

    ir: WidgetIrNode | None = None
    if resolved_ir_by_id is not None:
        candidate = resolved_ir_by_id.get(node.id)
        if candidate is not None and candidate.kind == WidgetIrKind.CHIP_CHOICE:
            ir = candidate

    structural = layout_fact_stack_circular_option_glyph_host(
        node
    ) or is_tag_component_chip_row(node)
    if ir is None and not structural:
        return None
    if ir is None:
        ir = WidgetIrNode(
            figma_id=node.id,
            kind=WidgetIrKind.CHIP_CHOICE,
            is_selected=chip_component_selected(node),
        )

    if isinstance(ctx, LayoutRenderContext):
        ir_ctx = IrEmitContext(
            uses_svg=ctx.uses_svg,
            theme_variant=ctx.theme_variant,
            responsive_enabled=ctx.responsive_enabled,
            bundled_font_families=ctx.bundled_font_families,
            dart_weight_overrides_by_family=ctx.dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=ctx.text_theme_slot_by_style_name,
            text_theme_size_slots=ctx.text_theme_size_slots,
        )
    elif isinstance(ctx, IrEmitContext):
        ir_ctx = ctx
    else:
        ir_ctx = IrEmitContext(uses_svg=False, responsive_enabled=False)

    return emit_chip_choice_layout(ir, clean=node, ctx=ir_ctx)

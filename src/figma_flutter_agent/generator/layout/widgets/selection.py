"""Inline payment and option-card selection indicators."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.style import (
    dart_color_expr,
    text_style_expr,
    text_widget_trailing_params,
)
from figma_flutter_agent.generator.layout.style.colors import is_greenish_fill
from figma_flutter_agent.generator.layout.style.decoration import _border_color_expr
from figma_flutter_agent.generator.layout.style.facts import selected_from_variant_or_luminance
from figma_flutter_agent.parser.interaction.shared import _descendant_nodes
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _selected_badge_fill_expr(margin_node: CleanDesignTreeNode) -> str:
    """Return badge fill from a greenish painted node in the margin subtree."""
    for item in _descendant_nodes(margin_node, 5):
        if is_greenish_fill(item.style.background_color):
            return dart_color_expr(
                item.style,
                fallback="Theme.of(context).colorScheme.primary",
            )
    return "Theme.of(context).colorScheme.primary"


def render_compact_trailing_selection_glyph(
    node: CleanDesignTreeNode,
    *,
    selected: bool = True,
) -> str:
    """Emit a small circular trailing selection check without Material button chrome."""
    width = float(node.sizing.width or 12.0)
    height = float(node.sizing.height or 12.0)
    width_lit = format_geometry_literal(width)
    height_lit = format_geometry_literal(height)
    badge_size = format_geometry_literal(min(width, height, 16.0))
    if not selected:
        return (
            f"SizedBox(width: {width_lit}, height: {height_lit}, child: Center(child: "
            f"Container(width: {badge_size}, height: {badge_size}, "
            "decoration: BoxDecoration("
            "color: Theme.of(context).colorScheme.surface, "
            "shape: BoxShape.circle, "
            "border: Border.all("
            "color: Theme.of(context).colorScheme.outline, width: 1.0)))))"
        )
    fill_expr = "Color(0xFF006FFD)"
    for item in _descendant_nodes(node, 3):
        if item.style.background_color:
            fill_expr = dart_color_expr(
                item.style,
                fallback="Color(0xFF006FFD)",
            )
            break
    return (
        f"SizedBox(width: {width_lit}, height: {height_lit}, child: Center(child: "
        f"Container(width: {badge_size}, height: {badge_size}, "
        f"decoration: BoxDecoration(color: {fill_expr}, shape: BoxShape.circle), "
        "child: Icon(Icons.check, color: Colors.white, size: 8.0))))"
    )


def render_payment_selection_indicator(
    node: CleanDesignTreeNode,
    *,
    selected: bool,
) -> str:
    """Emit a trailing circular radio/check affordance for payment option cards."""
    width = float(node.sizing.width or 20.0)
    height = float(node.sizing.height or 24.0)
    width_lit = format_geometry_literal(width)
    height_lit = format_geometry_literal(height)
    badge_size = format_geometry_literal(min(width, 20.0))
    if selected:
        fill_expr = _selected_badge_fill_expr(node)
        check_color = "Theme.of(context).colorScheme.onPrimary"
        badge = (
            f"Container(width: {badge_size}, height: {badge_size}, "
            f"decoration: BoxDecoration("
            f"color: {fill_expr}, shape: BoxShape.circle), "
            f"child: Icon(Icons.check, color: {check_color}, size: 12.0))"
        )
    else:
        from figma_flutter_agent.parser.interaction.selection import (
            payment_selection_circle_node,
        )

        circle = payment_selection_circle_node(node)
        if circle is not None and circle.style.background_color:
            fill = dart_color_expr(
                circle.style,
                fallback="Theme.of(context).colorScheme.surface",
            )
        else:
            fill = "Theme.of(context).colorScheme.surface"
        border = _border_color_expr(circle.style) if circle is not None else None
        if border is None:
            border = "Theme.of(context).colorScheme.outline"
        badge = (
            f"Container(width: {badge_size}, height: {badge_size}, "
            "decoration: BoxDecoration("
            f"color: {fill}, "
            "shape: BoxShape.circle, "
            f"border: Border.all(color: {border}, width: 1.0)))"
        )
    return f"SizedBox(width: {width_lit}, height: {height_lit}, child: Center(child: {badge}))"


def _hosts_indicator_column(child: CleanDesignTreeNode) -> bool:
    from figma_flutter_agent.parser.interaction.selection import (
        layout_fact_hosts_payment_selection_indicator,
    )

    if layout_fact_hosts_payment_selection_indicator(child):
        return True
    return any(
        layout_fact_hosts_payment_selection_indicator(grandchild) for grandchild in child.children
    )


def _find_payment_option_row(button: CleanDesignTreeNode) -> CleanDesignTreeNode | None:
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    for item in _descendant_nodes(button, 5):
        if item.type != NodeType.ROW or len(item.children) < 2:
            continue
        if any(_hosts_indicator_column(child) for child in item.children):
            return item
    return None


def _payment_option_text_lines(host: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    from figma_flutter_agent.parser.interaction.shared import _descendant_nodes

    return [
        item
        for item in _descendant_nodes(host, 4)
        if item.type == NodeType.TEXT and (item.text or "").strip()
    ]


def _payment_subtitle_has_figma_line_break(text: str) -> bool:
    """Return True when Figma authored an explicit multi-line subtitle."""
    lines = [part.strip() for part in text.splitlines() if part.strip()]
    return len(lines) >= 2


def _payment_option_display_text(text: str, *, multiline: bool) -> str:
    """Normalize payment-card subtitle copy for single- or multi-line emit."""
    if multiline:
        return text
    return " ".join(part.strip() for part in text.splitlines() if part.strip())


def try_render_payment_option_card_body(
    node: CleanDesignTreeNode,
    *,
    bundled_font_families: frozenset[str] | None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None,
    text_theme_slot_by_style_name: dict[str, str] | None,
    text_theme_size_slots: list[tuple[float, str]] | None,
) -> str | None:
    """Centered payment-card row with Figma-faithful subtitles and trailing radio."""
    from figma_flutter_agent.parser.interaction.selection import (
        button_is_payment_option_card,
        layout_fact_hosts_payment_selection_indicator,
    )

    if not button_is_payment_option_card(node):
        return None
    row = _find_payment_option_row(node)
    if row is None:
        return None
    indicator_host = next(child for child in row.children if _hosts_indicator_column(child))
    indicator_leaf = indicator_host
    if not layout_fact_hosts_payment_selection_indicator(indicator_host):
        indicator_leaf = next(
            child
            for child in indicator_host.children
            if layout_fact_hosts_payment_selection_indicator(child)
        )
    primary_host = next(child for child in row.children if child.id != indicator_host.id)
    text_lines = _payment_option_text_lines(primary_host)
    if not text_lines:
        return None
    title = text_lines[0]
    subtitle = text_lines[1] if len(text_lines) > 1 else None
    title_style = text_style_expr(
        title,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
        omit_line_height=True,
    )
    title_trailing = text_widget_trailing_params(
        title.style,
        omit_strut=True,
        optical_center=True,
    )
    title_widget = (
        f"Semantics(label: '{escape_dart_string(title.accessibility_label or title.text or title.name)}', "
        f"child: Text('{escape_dart_string(title.text or '')}', "
        f"style: {title_style}, {title_trailing}))"
    )
    column_children = [title_widget]
    if subtitle is not None:
        subtitle_multiline = _payment_subtitle_has_figma_line_break(subtitle.text or "")
        subtitle_style = text_style_expr(
            subtitle,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
            omit_line_height=True,
        )
        if subtitle_multiline:
            subtitle_trailing = text_widget_trailing_params(
                subtitle.style,
                omit_strut=True,
            )
            subtitle_trailing = f"{subtitle_trailing}, maxLines: 2"
        else:
            subtitle_trailing = text_widget_trailing_params(
                subtitle.style,
                omit_strut=True,
                optical_center=True,
                soft_wrap=False,
                clip_single_line=True,
            )
        subtitle_display = _payment_option_display_text(
            subtitle.text or "",
            multiline=subtitle_multiline,
        )
        column_children.append(
            f"Semantics(label: '{escape_dart_string(subtitle.accessibility_label or subtitle_display or subtitle.name)}', "
            f"child: Text('{escape_dart_string(subtitle_display)}', "
            f"style: {subtitle_style}, {subtitle_trailing}))"
        )
    spacing = 4.0
    if primary_host.type == NodeType.COLUMN and primary_host.spacing:
        spacing = min(float(primary_host.spacing), 4.0)
    spacing_lit = format_geometry_literal(spacing)
    copy_column = (
        "Column("
        "mainAxisSize: MainAxisSize.min, "
        "crossAxisAlignment: CrossAxisAlignment.start, "
        f"spacing: {spacing_lit}, "
        f"children: [{', '.join(column_children)}]"
        ")"
    )
    indicator = render_payment_selection_indicator(
        indicator_leaf,
        selected=selected_from_variant_or_luminance(indicator_leaf),
    )
    return (
        "Row("
        "mainAxisAlignment: MainAxisAlignment.spaceBetween, "
        "crossAxisAlignment: CrossAxisAlignment.center, "
        f"children: [Expanded(child: {copy_column}), {indicator}])"
    )

"""Figma-fact-driven style expressions for deterministic emit."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.colors import (
    dart_color_expr,
    fill_luminance,
    is_dark_fill_color,
    is_greenish_fill,
)
from figma_flutter_agent.generator.variant.state import variant_is_checked
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle

_NEAR_BLACK_LUMINANCE = 0.15
_ON_DARK_LABEL = "Theme.of(context).colorScheme.onPrimary"
_ON_LIGHT_LABEL = "Theme.of(context).colorScheme.onSurface"
_ON_DARK_LABEL_LITERAL = "Theme.of(context).colorScheme.onPrimary"  # lint:allow test-token-fallback


def is_near_black_fill(value: str | None) -> bool:
    """Return True when a fill reads as near-black."""
    luminance = fill_luminance(value)
    return luminance is not None and luminance < _NEAR_BLACK_LUMINANCE


def selected_from_variant_or_luminance(node: CleanDesignTreeNode) -> bool:
    """Infer selected/checked state from variant facts or dark row surface."""
    from figma_flutter_agent.parser.interaction.chip_variant import chip_component_selected

    if variant_is_checked(node) or chip_component_selected(node):
        return True
    return is_dark_fill_color(node.style.background_color)


def label_color_on_surface_expr(
    text_style: NodeStyle,
    *,
    surface_color: str | None,
    use_theme_tokens: bool = True,
) -> str:
    """Return label foreground for text sitting on a painted surface."""
    on_dark = is_dark_fill_color(surface_color)
    text_color = text_style.text_color
    if on_dark and (not text_color or is_near_black_fill(text_color)):
        return _ON_DARK_LABEL if use_theme_tokens else _ON_DARK_LABEL_LITERAL
    return dart_color_expr(
        text_style,
        css_key="color",
        fallback=_ON_DARK_LABEL if on_dark else _ON_LIGHT_LABEL,
    )


def chip_row_palette_exprs(
    chip_row: CleanDesignTreeNode,
) -> tuple[str, str]:
    """Return ``(background, foreground)`` Dart expressions for a chip row."""
    from figma_flutter_agent.parser.interaction.chip_variant import (
        chip_component_label_text_node,
    )

    text_node = chip_component_label_text_node(chip_row)
    background = dart_color_expr(
        chip_row.style,
        fallback="Theme.of(context).colorScheme.surfaceContainerHighest",
    )
    if text_node is not None:
        foreground = label_color_on_surface_expr(
            text_node.style,
            surface_color=chip_row.style.background_color,
        )
    else:
        on_dark = is_dark_fill_color(chip_row.style.background_color)
        foreground = _ON_DARK_LABEL if on_dark else _ON_LIGHT_LABEL
    return background, foreground

"""Public text style emitters."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.style.text_helpers import (
    _theme_text_style_expr,
    should_emit_strut_style,
)
from figma_flutter_agent.generator.theme_typography import (
    metrics_for_text_theme_slot,
    resolve_text_theme_slot,
)
from figma_flutter_agent.generator.variant.state import variant_font_size
from figma_flutter_agent.generator.theme_typography import (
    metrics_for_text_theme_slot,
    resolve_text_theme_slot,
)
from figma_flutter_agent.generator.variant.state import variant_font_size
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    NodeStyle,
    NodeType,
    TextSpanPart,
)

def filled_button_label_text_color(
    node: CleanDesignTreeNode,
    parent: CleanDesignTreeNode,
) -> str | None:
    """Return ``Color(0xFFFFFFFF)`` when *node* is the primary label of a filled button.

    A text node is considered a primary label when:
    1. Its parent stack contains at least one CONTAINER sibling with a non-None
       ``background_color`` (the button fill).
    2. The text node is in the top half of the parent stack (its vertical
       centre ≤ ``parent.sizing.height / 2``).

    Args:
        node: A TEXT node to test.
        parent: Parent STACK node.

    Returns:
        ``"Color(0xFFFFFFFF)"`` for primary labels; ``None`` otherwise.
    """
    if node.type != NodeType.TEXT:
        return None
    if parent.type == NodeType.BUTTON:
        if parent.style.background_color is None:
            return None
        first_text = next(
            (child for child in parent.children if child.type == NodeType.TEXT),
            None,
        )
        if first_text is None or first_text.id != node.id:
            return None
        return "Color(0xFFFFFFFF)"
    if parent.type != NodeType.STACK:
        return None
    has_fill = any(
        child.type == NodeType.CONTAINER and child.style.background_color is not None
        for child in parent.children
    )
    if not has_fill:
        return None
    # Only the primary (first) TEXT child of a filled stack gets forced-white label colour.
    # Secondary labels and footers that follow it are intentionally not overridden.
    first_text = next(
        (child for child in parent.children if child.type == NodeType.TEXT), None
    )
    if first_text is None or first_text.id != node.id:
        return None
    return "Color(0xFFFFFFFF)"


def text_style_expr(
    node: CleanDesignTreeNode,
    *,
    parent_node: CleanDesignTreeNode | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    design_tokens: DesignTokens | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    omit_line_height_for_strut: bool = False,
    omit_line_height: bool = False,
) -> str:
    """Build a theme-backed text style expression for a clean-tree text node."""
    style = node.style
    if parent_node is not None:
        label_color = filled_button_label_text_color(node, parent_node)
        if label_color is not None and style.text_color is None:
            style = style.model_copy(update={"text_color": "0xFFFFFFFF"})
    slot_map = text_theme_slot_by_style_name or {}
    size_slots = text_theme_size_slots or []
    slot, theme_matched = resolve_text_theme_slot(
        style,
        slot_by_style_name=slot_map,
        size_slots=size_slots,
    )
    ref_size, ref_weight = metrics_for_text_theme_slot(
        slot,
        size_slots,
        design_tokens,
    )
    variant_size = variant_font_size(node) if style.font_size is None else None
    return _theme_text_style_expr(
        style,
        slot=slot,
        theme_token_matched=theme_matched,
        reference_font_size=ref_size,
        reference_font_weight=ref_weight,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        variant_font_size_expr=variant_size,
        omit_line_height_for_strut=omit_line_height_for_strut,
        omit_line_height=omit_line_height,
    )


def text_span_style_expr(
    part: TextSpanPart,
    base_style: NodeStyle,
    *,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
) -> str:
    """Build a theme-backed style expression for one rich-text span."""
    style = NodeStyle(
        text_color=part.text_color or base_style.text_color,
        font_size=base_style.font_size,
        font_weight=part.font_weight or base_style.font_weight,
        line_height=base_style.line_height,
        letter_spacing=base_style.letter_spacing,
        font_family=base_style.font_family,
        font_style=base_style.font_style,
        text_decoration=part.text_decoration or base_style.text_decoration,
        style_name=base_style.style_name,
    )
    slot_map = text_theme_slot_by_style_name or {}
    size_slots = text_theme_size_slots or []
    slot, theme_matched = resolve_text_theme_slot(
        style,
        slot_by_style_name=slot_map,
        size_slots=size_slots,
    )
    return _theme_text_style_expr(
        style,
        slot=slot,
        theme_token_matched=theme_matched,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
    )

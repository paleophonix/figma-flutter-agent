"""Bracket-safe ``Text.rich`` / ``TextSpan`` emission for deterministic codegen."""

from __future__ import annotations

from figma_flutter_agent.generator.layout_common import escape_dart_string
from figma_flutter_agent.generator.layout_style import text_span_style_expr
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, TextSpanPart


def emit_text_span_child(
    part: TextSpanPart,
    base_style: NodeStyle,
    *,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
) -> str:
    chunk = escape_dart_string(part.text)
    span_style = text_span_style_expr(
        part,
        base_style,
        bundled_font_families=bundled_font_families,
        dart_weight_overrides_by_family=dart_weight_overrides_by_family,
        text_theme_slot_by_style_name=text_theme_slot_by_style_name,
        text_theme_size_slots=text_theme_size_slots,
    )
    if part.is_link:
        return (
            f"TextSpan(text: '{chunk}', style: {span_style}, "
            "recognizer: TapGestureRecognizer()..onTap = () {})"
        )
    return f"TextSpan(text: '{chunk}', style: {span_style})"


def emit_text_span_children_from_node(
    node: CleanDesignTreeNode,
    *,
    bundled_font_families: frozenset[str] | None = None,
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None,
    text_theme_slot_by_style_name: dict[str, str] | None = None,
    text_theme_size_slots: list[tuple[float, str]] | None = None,
) -> list[str]:
    return [
        emit_text_span_child(
            part,
            node.style,
            bundled_font_families=bundled_font_families,
            dart_weight_overrides_by_family=dart_weight_overrides_by_family,
            text_theme_slot_by_style_name=text_theme_slot_by_style_name,
            text_theme_size_slots=text_theme_size_slots,
        )
        for part in node.text_spans
    ]


def emit_text_rich(
    span_children: list[str],
    *,
    text_align_suffix: str = "",
    include_text_scaler: bool = True,
    compact: bool = True,
) -> str:
    spans_body = ", ".join(span_children)
    align = text_align_suffix
    scaler = "textScaler: textScaler" if include_text_scaler else ""
    use_compact = compact and not include_text_scaler
    if use_compact:
        return f"Text.rich(TextSpan(children: [{spans_body}]){align})"
    parts = [
        "Text.rich(",
        f"  TextSpan(children: [{spans_body}]),",
    ]
    if scaler:
        parts.append(f"  {scaler},")
    if align.startswith(", "):
        parts.append(f"  {align.removeprefix(', ')},")
    elif align:
        parts.append(f"  {align},")
    parts.append(")")
    return "\n".join(parts)

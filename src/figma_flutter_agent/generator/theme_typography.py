"""Map design typography tokens to Material ``TextTheme`` slots for codegen."""

from __future__ import annotations

import re

from figma_flutter_agent.schemas import DesignTokens, NodeStyle

TEXT_THEME_SLOTS: tuple[str, ...] = (
    "displayLarge",
    "headlineLarge",
    "titleLarge",
    "titleMedium",
    "bodyLarge",
    "bodyMedium",
    "bodySmall",
    "labelLarge",
)

_DEFAULT_TEXT_THEME_SLOT = "bodyMedium"


def normalize_typography_key(name: str) -> str:
    """Normalize a Figma or token style name for lookup."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def build_text_theme_slot_by_style_name(tokens: DesignTokens) -> dict[str, str]:
    """Map typography token names and normalized aliases to ``TextTheme`` slots."""
    typography = [
        {"style_name": name, "font_size": style.font_size, "font_weight": style.font_weight}
        for name, style in tokens.typography.items()
    ]
    if not typography:
        return {}
    ordered = sorted(typography, key=lambda item: float(item["font_size"]), reverse=True)
    slot_map: dict[str, str] = {}
    for slot, style in zip(TEXT_THEME_SLOTS, ordered, strict=False):
        style_name = str(style["style_name"])
        slot_map[style_name] = slot
        slot_map[normalize_typography_key(style_name)] = slot
    return slot_map


def build_text_theme_size_slots(tokens: DesignTokens) -> list[tuple[float, str]]:
    """Return ``(font_size, textTheme_slot)`` pairs sorted by descending font size."""
    typography = [
        {"style_name": name, "font_size": style.font_size, "font_weight": style.font_weight}
        for name, style in tokens.typography.items()
    ]
    if not typography:
        return []
    ordered = sorted(typography, key=lambda item: float(item["font_size"]), reverse=True)
    return [
        (float(style["font_size"]), slot)
        for slot, style in zip(TEXT_THEME_SLOTS, ordered, strict=False)
    ]


def resolve_text_theme_slot(
    style: NodeStyle,
    *,
    slot_by_style_name: dict[str, str],
    size_slots: list[tuple[float, str]],
) -> tuple[str, bool]:
    """Resolve a ``TextTheme`` slot and whether the node uses a named theme token.

    Args:
        style: Parsed node style.
        slot_by_style_name: Output of ``build_text_theme_slot_by_style_name``.
        size_slots: Output of ``build_text_theme_size_slots``.

    Returns:
        Material text theme slot name and whether ``style.style_name`` matched a theme token.
    """
    style_name = (style.style_name or "").strip()
    if style_name:
        if style_name in slot_by_style_name:
            return slot_by_style_name[style_name], True
        normalized = normalize_typography_key(style_name)
        if normalized in slot_by_style_name:
            return slot_by_style_name[normalized], True
    if style.font_size is not None and size_slots:
        target = float(style.font_size)
        for size, slot in size_slots:
            if target >= size - 0.5:
                return slot, False
        return size_slots[-1][1], False
    return _DEFAULT_TEXT_THEME_SLOT, False

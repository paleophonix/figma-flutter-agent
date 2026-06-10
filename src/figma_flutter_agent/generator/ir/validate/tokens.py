"""Design token snapping for IR overrides."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.layout.style.colors import _normalize_hex_color
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    WidgetIrOverrides,
)

_FONT_SIZE_SNAP_TOLERANCE = 0.75
_MAX_COLOR_SNAP_CHANNEL_DELTA = 24


@dataclass(frozen=True)
class _TokenRegistry:
    colors: frozenset[str]
    color_by_name: dict[str, str]
    font_sizes: frozenset[float]


def _normalize_token_color(value: str) -> str | None:
    trimmed = value.strip()
    if trimmed.startswith("#") and len(trimmed) == 7:
        return f"0xFF{trimmed[1:].upper()}"
    if trimmed.lower().startswith("0x"):
        body = trimmed[2:].upper()
        if len(body) == 6:
            return f"0xFF{body}"
        if len(body) == 8:
            return f"0x{body}"
    return _normalize_hex_color(value)


def _build_token_registry(tokens: DesignTokens) -> _TokenRegistry:
    colors: set[str] = set()
    color_by_name: dict[str, str] = {}
    for name, value in tokens.colors.items():
        normalized = _normalize_token_color(value)
        if normalized is not None:
            colors.add(normalized)
            color_by_name[name] = normalized
    font_sizes: set[float] = set()
    for style in tokens.typography.values():
        font_sizes.add(round(style.font_size, 2))
    return _TokenRegistry(
        colors=frozenset(colors),
        color_by_name=color_by_name,
        font_sizes=frozenset(font_sizes),
    )


def _collect_clean_tree_token_colors(root: CleanDesignTreeNode) -> frozenset[str]:
    """Colors observed on parsed nodes (Figma truth beyond deduped flat token keys)."""
    colors: set[str] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        style = node.style
        for raw in (
            style.text_color,
            style.background_color,
            style.border_color,
        ):
            if raw is None:
                continue
            normalized = _normalize_token_color(raw)
            if normalized is not None:
                colors.add(normalized)
        for child in node.children:
            walk(child)

    walk(root)
    return frozenset(colors)


def _collect_clean_tree_font_sizes(root: CleanDesignTreeNode) -> frozenset[float]:
    """Font sizes observed on parsed text nodes (Figma truth beyond deduped typography)."""
    sizes: set[float] = set()

    def walk(node: CleanDesignTreeNode) -> None:
        font_size = node.style.font_size
        if font_size is not None and font_size > 0:
            sizes.add(round(font_size, 2))
        for child in node.children:
            walk(child)

    walk(root)
    return frozenset(sizes)


def _merge_token_registry_with_clean_tree(
    registry: _TokenRegistry,
    root: CleanDesignTreeNode,
) -> _TokenRegistry:
    """Allow IR overrides to reference colors and font sizes present on the clean tree."""
    extra_colors = _collect_clean_tree_token_colors(root)
    extra_font_sizes = _collect_clean_tree_font_sizes(root)
    if not extra_colors and not extra_font_sizes:
        return registry
    return _TokenRegistry(
        colors=registry.colors | extra_colors,
        color_by_name=registry.color_by_name,
        font_sizes=registry.font_sizes | extra_font_sizes,
    )


def _color_rgb(hex_literal: str) -> tuple[int, int, int] | None:
    normalized = _normalize_token_color(hex_literal)
    if normalized is None:
        return None
    channels = normalized.removeprefix("0x").removeprefix("0X")
    if len(channels) != 8:
        return None
    value = int(channels, 16)
    return (value >> 16) & 255, (value >> 8) & 255, value & 255


def _nearest_token_color(value: str, registry: _TokenRegistry) -> str | None:
    source = _color_rgb(value)
    if source is None or not registry.colors:
        return None
    best: str | None = None
    best_distance = float("inf")
    for candidate in registry.colors:
        target = _color_rgb(candidate)
        if target is None:
            continue
        distance = sum(abs(source[index] - target[index]) for index in range(3))
        if distance < best_distance:
            best_distance = distance
            best = candidate
    if best is None or best_distance > _MAX_COLOR_SNAP_CHANNEL_DELTA * 3:
        return None
    return best


def _nearest_token_font_size(value: float, registry: _TokenRegistry) -> float | None:
    if not registry.font_sizes:
        return None
    nearest = min(registry.font_sizes, key=lambda size: abs(size - value))
    if abs(nearest - value) > _FONT_SIZE_SNAP_TOLERANCE:
        return None
    return nearest


def _resolve_token_color(value: str, registry: _TokenRegistry) -> str | None:
    trimmed = value.strip()
    by_name = registry.color_by_name.get(trimmed)
    if by_name is not None:
        return by_name
    normalized = _normalize_token_color(trimmed)
    if normalized is not None and normalized in registry.colors:
        return normalized
    return _nearest_token_color(trimmed, registry)


def _snap_ir_overrides_to_tokens(
    overrides: WidgetIrOverrides,
    *,
    figma_id: str,
    registry: _TokenRegistry,
    soft_invalid: bool = False,
) -> WidgetIrOverrides:
    updates: dict[str, object] = {}
    if overrides.text_color is not None:
        resolved = _resolve_token_color(overrides.text_color, registry)
        if resolved is None:
            if soft_invalid:
                logger.warning(
                    "Dropped screenIr override textColor for {}: {!r} is not a registered token",
                    figma_id,
                    overrides.text_color,
                )
                updates["text_color"] = None
            else:
                raise GenerationError(
                    f"IR overrides for {figma_id!r} textColor {overrides.text_color!r} "
                    "is not a registered design token color"
                )
        elif resolved != overrides.text_color:
            updates["text_color"] = resolved
    if overrides.background_color is not None:
        resolved = _resolve_token_color(overrides.background_color, registry)
        if resolved is None:
            if soft_invalid:
                logger.warning(
                    "Dropped screenIr override backgroundColor for {}: {!r} is not a registered token",
                    figma_id,
                    overrides.background_color,
                )
                updates["background_color"] = None
            else:
                raise GenerationError(
                    f"IR overrides for {figma_id!r} backgroundColor "
                    f"{overrides.background_color!r} is not a registered design token color"
                )
        elif resolved != overrides.background_color:
            updates["background_color"] = resolved
    if overrides.font_size is not None:
        rounded = round(overrides.font_size, 2)
        if rounded in registry.font_sizes:
            if rounded != overrides.font_size:
                updates["font_size"] = rounded
        else:
            snapped = _nearest_token_font_size(overrides.font_size, registry)
            if snapped is None:
                if soft_invalid:
                    logger.warning(
                        "Dropped screenIr override fontSize for {}: {} is not a registered token",
                        figma_id,
                        overrides.font_size,
                    )
                    updates["font_size"] = None
                else:
                    raise GenerationError(
                        f"IR overrides for {figma_id!r} fontSize {overrides.font_size} "
                        "is not a registered typography token size"
                    )
            else:
                updates["font_size"] = snapped
    if not updates:
        return overrides
    return overrides.model_copy(update=updates)

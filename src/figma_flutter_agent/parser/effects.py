"""Figma effect and gradient extraction."""

from __future__ import annotations

import math
from typing import Any

from figma_flutter_agent.parser.numeric_rounding import round_geometry, round_micro_style
from figma_flutter_agent.parser.tokens.colors import rgba_to_argb_hex
from figma_flutter_agent.schemas import CornerRadii, GradientFill, GradientStop, ShadowEffect


def extract_layer_blur(node: dict[str, Any]) -> float | None:
    """Extract visible layer blur radius from Figma effects."""
    layer, _ = extract_blur_effects(node)
    return layer


def extract_blur_effects(node: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract ``LAYER_BLUR`` and ``BACKGROUND_BLUR`` radii separately."""
    layer_blur: float | None = None
    background_blur: float | None = None
    for effect in node.get("effects") or []:
        if effect.get("visible") is False:
            continue
        effect_type = effect.get("type")
        radius = effect.get("radius")
        if radius is None:
            continue
        value = float(radius)
        if effect_type == "LAYER_BLUR":
            layer_blur = value
        elif effect_type == "BACKGROUND_BLUR":
            background_blur = value
    return layer_blur, background_blur


def parse_corner_radii(node: dict[str, Any]) -> CornerRadii | None:
    raw = node.get("rectangleCornerRadii")
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        values = [round_micro_style(float(value)) or 0.0 for value in raw]
    except (TypeError, ValueError):
        return None
    return CornerRadii(
        top_left=values[0],
        top_right=values[1],
        bottom_right=values[2],
        bottom_left=values[3],
    )


def extract_shadow_effects(node: dict[str, Any]) -> list[ShadowEffect]:
    """Extract visible drop and inner shadows from a Figma node."""
    effects: list[ShadowEffect] = []
    for effect in node.get("effects") or []:
        if effect.get("visible") is False:
            continue
        effect_type = effect.get("type")
        if effect_type not in {"DROP_SHADOW", "INNER_SHADOW"}:
            continue
        color_payload = effect.get("color") or {}
        effects.append(
            ShadowEffect(
                kind="inner" if effect_type == "INNER_SHADOW" else "drop",
                offset_x=round_geometry(float(effect.get("offset", {}).get("x", 0))) or 0.0,
                offset_y=round_geometry(float(effect.get("offset", {}).get("y", 0))) or 0.0,
                blur=float(effect.get("radius", 0)),
                spread=float(effect.get("spread", 0)),
                color=rgba_to_argb_hex(color_payload),
            )
        )
    return effects


def extract_gradient_fill(fills: list[dict[str, Any]]) -> GradientFill | None:
    """Extract the first visible gradient fill from Figma fills."""
    for fill in fills:
        if fill.get("visible") is False:
            continue
        fill_type = fill.get("type")
        paint_opacity = float(fill.get("opacity", 1.0))
        if fill_type == "GRADIENT_LINEAR":
            stops = [
                GradientStop(
                    position=float(stop.get("position", 0)),
                    color=rgba_to_argb_hex(stop.get("color") or {}),
                )
                for stop in fill.get("gradientStops") or []
            ]
            angle = linear_gradient_angle(fill.get("gradientHandlePositions") or [])
            return GradientFill(type="linear", stops=stops, angle=angle, opacity=paint_opacity)
        if fill_type == "GRADIENT_RADIAL":
            stops = [
                GradientStop(
                    position=float(stop.get("position", 0)),
                    color=rgba_to_argb_hex(stop.get("color") or {}),
                )
                for stop in fill.get("gradientStops") or []
            ]
            return GradientFill(type="radial", stops=stops, opacity=paint_opacity)
    return None


def linear_gradient_angle(handles: list[dict[str, float]]) -> float | None:
    if len(handles) < 2:
        return None
    start = handles[0]
    end = handles[1]
    delta_x = end.get("x", 0) - start.get("x", 0)
    delta_y = end.get("y", 0) - start.get("y", 0)
    if delta_x == 0 and delta_y == 0:
        return None
    return round(math.degrees(math.atan2(delta_y, delta_x)), 2)


def derive_elevation(effects: list[ShadowEffect]) -> float | None:
    """Derive a Material-like elevation value from drop shadows."""
    drop_blurs = [effect.blur for effect in effects if effect.kind == "drop"]
    if not drop_blurs:
        return None
    return round(max(drop_blurs) / 4, 2)

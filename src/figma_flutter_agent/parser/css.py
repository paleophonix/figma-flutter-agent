"""CSS-like property synthesis from REST-derived node styles."""

from __future__ import annotations

from figma_flutter_agent.schemas import NodeStyle

_FIGMA_BLEND_TO_CSS: dict[str, str] = {
    "MULTIPLY": "multiply",
    "SCREEN": "screen",
    "OVERLAY": "overlay",
    "DARKEN": "darken",
    "LIGHTEN": "lighten",
    "COLOR_DODGE": "color-dodge",
    "COLOR_BURN": "color-burn",
    "HARD_LIGHT": "hard-light",
    "SOFT_LIGHT": "soft-light",
    "DIFFERENCE": "difference",
    "EXCLUSION": "exclusion",
    "HUE": "hue",
    "SATURATION": "saturation",
    "COLOR": "color",
    "LUMINOSITY": "luminosity",
}
_FIGMA_TEXT_ALIGN_TO_CSS: dict[str, str] = {
    "LEFT": "left",
    "RIGHT": "right",
    "CENTER": "center",
    "JUSTIFIED": "justify",
}


def argb_hex_to_css_rgba(hex_value: str) -> str:
    """Convert Flutter ARGB hex to CSS rgba() string."""
    normalized = hex_value.removeprefix("0x").removeprefix("0X")
    if len(normalized) != 8:
        return hex_value
    alpha = int(normalized[0:2], 16) / 255
    red = int(normalized[2:4], 16)
    green = int(normalized[4:6], 16)
    blue = int(normalized[6:8], 16)
    return f"rgba({red}, {green}, {blue}, {alpha:.3f})"


def build_css_properties(style: NodeStyle) -> dict[str, str]:
    """Build a complete CSS-like property dict from REST-synthesised NodeStyle fields."""
    css: dict[str, str] = {}

    if style.background_color:
        css["background-color"] = argb_hex_to_css_rgba(style.background_color)
    if style.text_color:
        css["color"] = argb_hex_to_css_rgba(style.text_color)
    if style.border_radius is not None:
        css["border-radius"] = f"{style.border_radius:g}px"
    if style.border_width is not None:
        css["border-width"] = f"{style.border_width:g}px"
    if style.border_color:
        css["border-color"] = argb_hex_to_css_rgba(style.border_color)
    if style.font_size is not None:
        css["font-size"] = f"{style.font_size:g}px"
    if style.font_weight:
        css["font-weight"] = style.font_weight.removeprefix("w")
    if style.font_family:
        css["font-family"] = style.font_family
    if style.font_style and style.font_style.lower() != "normal":
        css["font-style"] = style.font_style.lower()
    if style.text_align:
        css_align = _FIGMA_TEXT_ALIGN_TO_CSS.get(style.text_align.upper(), style.text_align.lower())
        css["text-align"] = css_align
    if style.line_height is not None:
        css["line-height"] = f"{style.line_height:g}"
    if style.letter_spacing is not None:
        css["letter-spacing"] = f"{style.letter_spacing:g}px"
    if style.opacity is not None:
        css["opacity"] = str(style.opacity)
    if style.blend_mode:
        css_blend = _FIGMA_BLEND_TO_CSS.get(style.blend_mode)
        if css_blend:
            css["mix-blend-mode"] = css_blend
    if style.layer_blur is not None:
        css["filter"] = f"blur({style.layer_blur:g}px)"
    if style.elevation is not None:
        css["elevation"] = str(style.elevation)
    if style.gradient:
        stop_values = ", ".join(
            f"{argb_hex_to_css_rgba(stop.color)} {int(stop.position * 100)}%"
            for stop in style.gradient.stops
        )
        if style.gradient.type == "linear":
            angle = style.gradient.angle if style.gradient.angle is not None else 180
            css["background"] = f"linear-gradient({angle}deg, {stop_values})"
        else:
            css["background"] = f"radial-gradient(circle, {stop_values})"
    if style.effects:
        shadow_values = []
        for effect in style.effects:
            inset = "inset " if effect.kind == "inner" else ""
            shadow_values.append(
                f"{inset}{effect.offset_x}px {effect.offset_y}px {effect.blur}px "
                f"{effect.spread}px {argb_hex_to_css_rgba(effect.color)}"
            )
        css["box-shadow"] = ", ".join(shadow_values)
    return css

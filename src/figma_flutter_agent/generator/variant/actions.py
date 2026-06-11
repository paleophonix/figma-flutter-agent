"""Generated callback expressions for variant-backed controls."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.variant.state import (
    get_variant_property,
    variant_blocks_interaction,
    variant_is_checked,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode


def toggle_value_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart bool expression for Checkbox/Switch value."""
    return "true" if variant_is_checked(node) else "false"


def slider_value_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart double literal for Slider value from variant Value (0-1 or 0-100)."""
    raw = get_variant_property(node, "value", "progress", "position")
    if raw is None:
        return "0.5"
    try:
        numeric = float(raw.replace("%", "").strip())
    except ValueError:
        return "0.5"
    if numeric > 1.0:
        numeric /= 100.0
    clamped = min(1.0, max(0.0, numeric))
    return str(clamped)


def slider_on_changed_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart onChanged expression for Slider/CupertinoSlider."""
    if variant_blocks_interaction(node):
        return "null"
    zone = custom_code_zone_id(node.id, "slider-action")
    return f"(value) {{ {inline_custom_code_comment(zone)} }}"


def toggle_on_changed_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart onChanged expression for Checkbox/Switch."""
    if variant_blocks_interaction(node):
        return "null"
    zone = custom_code_zone_id(node.id, "toggle-action")
    return f"(value) {{ {inline_custom_code_comment(zone)} }}"


def button_on_pressed_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart expression for button onPressed."""
    if variant_blocks_interaction(node):
        return "null"
    zone = custom_code_zone_id(node.id, "button-action")
    return f"() {{ {inline_custom_code_comment(zone)} }}"

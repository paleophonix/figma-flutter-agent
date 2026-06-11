"""Accessibility auto_fix provenance and pixel-perfect policy (E0.4)."""

from __future__ import annotations

from figma_flutter_agent.config.profiles import apply_pixel_perfect_profile
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.parser.accessibility import apply_accessibility_fixes
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType


def _badge_tree(font_size: float) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="text:1",
        name="Badge",
        type=NodeType.TEXT,
        text="9",
        style=NodeStyle(font_size=font_size, text_color="0xFF333333"),
    )


def test_auto_fix_off_preserves_small_font() -> None:
    settings = apply_pixel_perfect_profile(Settings())
    tree = _badge_tree(9.0)
    if settings.agent.accessibility.auto_fix:
        tree = apply_accessibility_fixes(tree)
    assert tree.style.font_size == 9.0


def test_auto_fix_on_bumps_font_and_logs() -> None:
    from loguru import logger

    tree = _badge_tree(9.0)
    messages: list[str] = []

    def _sink(message):
        messages.append(message.record["message"])

    handler_id = logger.add(_sink, level="INFO")
    try:
        fixed = apply_accessibility_fixes(tree)
    finally:
        logger.remove(handler_id)

    assert fixed.style.font_size == 12.0
    assert any("field=font_size" in message for message in messages)

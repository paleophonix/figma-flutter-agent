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


def test_accessibility_style_mutation_allowed_at_cp1_without_provenance_recorder() -> None:
    """Parse-phase auto_fix runs before plan activates provenance (profile_edit regression)."""
    from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
        activate_conservation_session,
        clear_conservation_session,
        run_cp1_normalize,
        set_parse_style_baseline,
    )

    activate_conservation_session()
    try:
        tree = CleanDesignTreeNode(
            id="611:1338",
            name="Button",
            type=NodeType.BUTTON,
            style=NodeStyle(background_color="0xFF28A745"),
            children=[
                CleanDesignTreeNode(
                    id="611:1339",
                    name="Save",
                    type=NodeType.TEXT,
                    text="Save",
                    style=NodeStyle(text_color="0xFFFFFFFF", font_size=14.0),
                ),
            ],
        )
        set_parse_style_baseline(tree)
        fixed = apply_accessibility_fixes(tree)
        label = next(child for child in fixed.children if child.id == "611:1339")
        assert label.style.text_color != "0xFFFFFFFF"

        result = run_cp1_normalize(fixed, transform_fn=lambda source: source)
        assert result is fixed
    finally:
        clear_conservation_session()

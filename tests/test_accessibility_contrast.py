"""Tests for WCAG contrast hard gates."""

from __future__ import annotations

import pytest

from figma_flutter_agent.config import Settings, apply_production_profile
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.parser.accessibility import enforce_contrast_gates
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType


def _low_contrast_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.COLUMN,
        style=NodeStyle(background_color="0xFFFFFFFF"),
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="Muted label",
                type=NodeType.TEXT,
                text="Hello",
                style=NodeStyle(text_color="0xFFCCCCCC", font_size=14),
            )
        ],
    )


def test_enforce_contrast_gates_raises_on_low_contrast() -> None:
    with pytest.raises(FlutterProjectError, match="Low contrast"):
        enforce_contrast_gates(_low_contrast_tree())


def test_apply_production_profile_enables_strict_contrast_and_fail_fast_llm() -> None:
    settings = apply_production_profile(Settings())
    assert settings.agent.quality.strict_contrast is True
    assert settings.agent.accessibility.auto_fix is False
    assert settings.agent.generation.llm_fallback_to_deterministic is False

"""Artboard frame growth when intrinsic flow content exceeds Figma bbox."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.flex_policy.alignment import (
    flex_host_prefers_min_height_pin,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode

_HISTORY = Path(
    r"e:/@dev/flutter-demo-project/ataev/.figma_debug/processed/history_layout.json"
)


@pytest.mark.skipif(not _HISTORY.is_file(), reason="ataev fixture missing")
def test_history_background_column_prefers_min_height_pin() -> None:
    """Fixed 775px frame must not pin ``SizedBox(height: …)`` when flow cards grow."""
    raw = json.loads(_HISTORY.read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(raw["cleanTree"])
    background = root.children[0]
    assert flex_host_prefers_min_height_pin(background)
    layout = render_layout_file(root, feature_name="history", uses_svg=False)[
        "lib/generated/history_layout.dart"
    ]
    assert "SizedBox(height: 775.0, child: Container(" not in layout
    assert "ConstrainedBox(constraints: BoxConstraints(minHeight: 775.0)" in layout

"""Regression laws for mixed inflow stack overlays (sign_up_version_5 family)."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.schemas import CleanDesignTreeNode


def test_sign_up_version_5_absolute_overlay_is_direct_stack_child() -> None:
    """Law: positioned_widget_must_be_direct_child_of_stack."""
    processed = json.loads(
        Path(".debug/screen/limbo/sign_up_version_5/processed.json").read_text(encoding="utf-8")
    )
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_5_overlay", uses_svg=True)[
        "lib/generated/sign_up_version_5_overlay_layout.dart"
    ]
    compact = layout.replace("\n", "")
    assert "figma-42_2283" in compact
    assert "SizedBox(width: double.infinity, child: Positioned(" not in compact

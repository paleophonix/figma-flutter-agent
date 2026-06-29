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


def test_sign_up_version_5_interleaved_absolute_emits_single_flow_column() -> None:
    """Law: stack_flow_children_coalesced_into_single_column."""
    processed = json.loads(
        Path(".debug/screen/limbo/sign_up_version_5/processed.json").read_text(encoding="utf-8")
    )
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    layout = render_layout_file(root, feature_name="sign_up_version_5_flow_column", uses_svg=True)[
        "lib/generated/sign_up_version_5_flow_column_layout.dart"
    ]
    compact = layout.replace("\n", "")
    content_idx = compact.find("figma-42_2282")
    assert content_idx >= 0
    content_chunk = compact[content_idx : content_idx + 20000]
    assert content_chunk.count(
        "Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, spacing: 24.0"
    ) == 1
    assert "Get Started now" in content_chunk
    assert "First Name" in content_chunk

"""Tests for AI UX report export."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.debug.paths import screen_root
from figma_flutter_agent.parser.ux_report import build_ai_ux_report, write_analysis_reports
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def test_write_analysis_reports_creates_json_files(
    debug_agent_root: Path,
    tmp_path: Path,
) -> None:
    root = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.STACK)
    written = write_analysis_reports(
        tmp_path,
        feature_slug="demo_screen",
        root=root,
        prototype_links=[],
        routing_type="none",
        dark_mode_enabled=False,
        write_ux_report=True,
        write_animation_manifest=True,
    )
    assert len(written) == 2
    screen_dir = screen_root(tmp_path, "demo_screen")
    ux_payload = json.loads((screen_dir / "ai_ux.json").read_text())
    assert "aiUxSuggestions" in ux_payload
    assert "animationManifest" in ux_payload
    anim_payload = json.loads((screen_dir / "animations.json").read_text())
    assert anim_payload["routingType"] == "none"


def test_build_ai_ux_report_includes_dark_mode_hint() -> None:
    root = CleanDesignTreeNode(id="1", name="Screen", type=NodeType.STACK)
    report = build_ai_ux_report(root, dark_mode_enabled=False)
    assert any("Dark mode is disabled" in item for item in report["animationSuggestions"])

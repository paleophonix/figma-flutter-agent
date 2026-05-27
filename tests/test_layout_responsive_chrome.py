"""Adaptive nav chrome: bottom bar on mobile, side rail on tablet/desktop."""

import json
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.planner import plan_from_figma_root


def test_shell_with_bottom_nav_uses_side_rail_layout_on_wide() -> None:
    root = json.loads(
        Path("tests/fixtures/figma_bottom_nav_sample.json").read_text(encoding="utf-8")
    )
    planned = plan_from_figma_root(root, Settings(), node_id=root["id"], package_name="demo_app")
    layout = planned["lib/generated/shell_screen_layout.dart"]

    assert "theme/app_layout.dart" in layout
    assert "_LayoutChromeNav(" in layout
    assert "NavigationRail(" in layout
    assert "NavigationRailDestination(" in layout
    assert "AppBreakpoints.isTablet(width)" in layout
    assert "crossAxisAlignment: CrossAxisAlignment.stretch" in layout
    assert "Expanded(child:" in layout

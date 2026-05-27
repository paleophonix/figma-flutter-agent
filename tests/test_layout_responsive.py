"""Tests for breakpoint-driven layout in deterministic renderer (spec §7.3)."""

import json
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.planner import plan_from_figma_root


def test_root_column_reflows_to_row_on_tablet_desktop() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, Settings(), node_id=root["id"], package_name="demo_app")
    layout = planned["lib/generated/onboarding_screen_layout.dart"]

    assert "theme/app_layout.dart" in layout
    assert "LayoutBuilder(" in layout
    assert "AppBreakpoints.isWideLayout(width)" in layout
    assert "Expanded(child:" in layout


def test_responsive_disabled_skips_layout_builder() -> None:
    settings = Settings()
    agent = settings.agent.model_copy(
        update={"responsive": settings.agent.responsive.model_copy(update={"enabled": False})}
    )
    settings = settings.model_copy(update={"agent": agent})
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, settings, node_id=root["id"], package_name="demo_app")
    layout = planned["lib/generated/onboarding_screen_layout.dart"]

    assert "LayoutBuilder(" not in layout

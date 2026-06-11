"""Tests for breakpoint-driven layout in deterministic renderer (spec §7.3)."""

import json
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.planner import plan_from_figma_root
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing


def test_phone_artboard_skips_column_reflow() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, Settings(), node_id=root["id"], package_name="demo_app")
    layout = planned["lib/generated/onboarding_screen_layout.dart"]

    assert "AppBreakpoints.isWideLayout(width)" not in layout


def test_wide_artboard_reflows_column_on_tablet_desktop() -> None:
    section = CleanDesignTreeNode(
        id="2",
        name="Hero",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="3", name="Left", type=NodeType.TEXT, text="Left"),
            CleanDesignTreeNode(id="4", name="Right", type=NodeType.TEXT, text="Right"),
        ],
    )
    screen = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=600.0, height=900.0),
        children=[section],
    )
    layout = render_layout_file(screen, feature_name="wide_hero", uses_svg=False)[
        "lib/generated/wide_hero_layout.dart"
    ]
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

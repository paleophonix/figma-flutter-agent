"""Regression tests for spec §7.3 breakpoints."""

import json
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.planner import plan_from_figma_root


def _layout_source() -> str:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, Settings(), node_id=root["id"])
    return planned["lib/theme/app_layout.dart"]


def test_breakpoints_match_spec_section_7_3() -> None:
    source = _layout_source()

    assert "mobileSmallMax = 480" in source
    assert "mobileLargeMax = 768" in source
    assert "tabletMax = 1024" in source
    assert "isTablet(double width) =>" in source
    assert "width > mobileLargeMax && width <= tabletMax" in source
    assert "isDesktop(double width) => width > tabletMax" in source


def test_breakpoints_classify_spec_ranges() -> None:
    source = _layout_source()

    assert "isMobileSmall(double width) => width <= mobileSmallMax" in source
    assert "isMobileLarge(double width)" in source
    assert "width > mobileSmallMax && width <= mobileLargeMax" in source
    assert "isWideLayout(double width) => width > mobileSmallMax" in source

"""Tests for the optional visual QA profile."""

import json
from pathlib import Path

from figma_flutter_agent.config import apply_visual_qa_profile, load_settings
from figma_flutter_agent.generator.planner import plan_from_figma_root


def _visual_qa_settings():
    example = Path(".ai-figma-flutter.yml.example")
    return apply_visual_qa_profile(load_settings(example))


def test_visual_qa_profile_enables_dark_mode_and_golden_test() -> None:
    settings = _visual_qa_settings()
    assert settings.agent.dark_mode.enabled is True
    assert settings.agent.validation.export_figma_reference is True
    assert settings.agent.validation.generate_golden_test is True
    assert settings.agent.validation.generate_typography_specimen_test is True
    assert settings.agent.validation.pixel_diff_threshold == 0.05


def test_plan_from_figma_root_emits_golden_scaffold_with_visual_profile() -> None:
    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    settings = _visual_qa_settings()
    planned = plan_from_figma_root(root, settings, node_id=str(root.get("id")))

    assert any(path.startswith("test/golden/") for path in planned)
    assert "test/golden/typography_specimens_test.dart" in planned
    assert "spec_01_btn" in planned["test/golden/typography_specimens_test.dart"]
    main_dart = planned.get("lib/main.dart", "")
    theme_dart = planned.get("lib/theme/app_theme.dart", "")
    assert "darkTheme" in main_dart or "ThemeMode" in main_dart
    assert "static ThemeData dark" in theme_dart or "darkTheme" in main_dart

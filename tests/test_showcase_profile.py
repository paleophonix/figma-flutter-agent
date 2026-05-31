"""Tests for optional showcase profile and YAML patching."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.config import Settings, apply_showcase_profile
from figma_flutter_agent.dev.showcase_yaml import apply_showcase_yaml
from figma_flutter_agent.generator.renderer import (
    inject_riverpod_consumer,
    showcase_provider_name,
)


def test_apply_showcase_profile_enables_optional_features() -> None:
    updated = apply_showcase_profile(Settings())
    assert updated.agent.state_management.type == "riverpod"
    assert updated.agent.dark_mode.enabled is True
    assert updated.agent.ux.write_report is True
    assert updated.agent.animations.write_manifest is True
    assert updated.agent.routing.type == "go_router"


def test_apply_showcase_yaml_merges_project_config(tmp_path: Path) -> None:
    config = tmp_path / ".ai-figma-flutter.yml"
    config.write_text(
        "state_management:\n  type: none\ndark_mode:\n  enabled: false\n",
        encoding="utf-8",
    )
    apply_showcase_yaml(tmp_path)
    text = config.read_text(encoding="utf-8")
    assert "riverpod" in text
    assert "enabled: true" in text


def test_inject_riverpod_consumer_wraps_build_return() -> None:
    source = """
class DemoScreen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const Placeholder();
  }
}
"""
    provider = showcase_provider_name("DemoScreen")
    patched = inject_riverpod_consumer(source, provider)
    assert "Consumer(" in patched
    assert f"ref.watch({provider})" in patched

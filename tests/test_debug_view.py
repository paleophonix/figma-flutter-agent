"""Tests for debug bundle preview deployment."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.debug.dart_bundle import build_dart_debug_bundle
from figma_flutter_agent.debug.paths import dart_debug_snapshot_path, emitter_reference_bundle_path
from figma_flutter_agent.dev.debug_view import (
    DebugViewSource,
    deploy_debug_bundle_to_project,
    discover_view_bundle_choices,
    launch_project_screen_in_chrome,
    resolve_debug_view_bundle_path,
    resolve_view_bundle_choice_input,
)
from figma_flutter_agent.errors import FlutterProjectError


def test_resolve_debug_view_bundle_paths(debug_agent_root: Path, tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    final = dart_debug_snapshot_path(project, "background", "final")
    final.parent.mkdir(parents=True)
    final.write_text("// bundle\n", encoding="utf-8")
    ref = emitter_reference_bundle_path(project, "background")
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text("// ref\n", encoding="utf-8")

    assert (
        resolve_debug_view_bundle_path(project, "background", DebugViewSource.DART_FINAL) == final
    )
    assert resolve_debug_view_bundle_path(project, "background", DebugViewSource.REFERENCE) == ref


def test_discover_view_bundle_choices_orders_reference_second(
    debug_agent_root: Path, tmp_path: Path
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    final = dart_debug_snapshot_path(project, "background", "final")
    ref = emitter_reference_bundle_path(project, "background")
    plan = dart_debug_snapshot_path(project, "background", "plan")
    for path in (final, ref, plan):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// bundle\n", encoding="utf-8")

    choices = discover_view_bundle_choices(project, "background")
    assert [choice.source for choice in choices] == [
        DebugViewSource.DART_FINAL,
        DebugViewSource.REFERENCE,
        DebugViewSource.DART_PLAN,
    ]
    assert resolve_view_bundle_choice_input("ref", choices) == 1
    assert resolve_view_bundle_choice_input("reference", choices) == 1
    assert resolve_view_bundle_choice_input("2", choices) == 1
    assert resolve_view_bundle_choice_input("3", choices) == 2


def test_launch_project_screen_in_chrome_requires_lib_screen(
    debug_agent_root: Path, tmp_path: Path
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    with pytest.raises(FlutterProjectError, match="Screen not found"):
        launch_project_screen_in_chrome(project, feature_name="missing_screen")


def test_resolve_debug_view_bundle_missing(debug_agent_root: Path, tmp_path: Path) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    with pytest.raises(FlutterProjectError, match="not found"):
        resolve_debug_view_bundle_path(project, "background", DebugViewSource.DART_FINAL)


def test_deploy_debug_bundle_writes_lib_files(
    debug_agent_root: Path, tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo\n", encoding="utf-8")
    agent_config = tmp_path / "agent"
    agent_config.mkdir()
    (agent_config / ".ai-figma-flutter.yml").write_text(
        "agent:\n  flutter:\n    architecture: feature_first\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FIGMA_FLUTTER_CONFIG", str(agent_config / ".ai-figma-flutter.yml"))

    planned = {
        "lib/features/home/home_screen.dart": """
import 'package:flutter/material.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}
""",
    }
    bundle = build_dart_debug_bundle(
        feature_name="home",
        planned_files=planned,
        package_name="demo",
    )
    assert bundle is not None
    bundle_path = dart_debug_snapshot_path(project, "home", "final")
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_path.write_text(bundle, encoding="utf-8")

    from figma_flutter_agent.config import Settings

    written = deploy_debug_bundle_to_project(
        project,
        bundle_path,
        feature_name="home",
        settings=Settings(),
    )

    assert "lib/features/home/home_screen.dart" in written
    assert "lib/main.dart" in written
    assert (project / "lib/main.dart").is_file()
    assert "HomeScreen" in (project / "lib/main.dart").read_text(encoding="utf-8")

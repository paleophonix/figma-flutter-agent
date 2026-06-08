"""Automated fixture-based demo sign-off (substitute for manual Figma+demo_app when offline)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from figma_flutter_agent.config import Settings
from figma_flutter_agent.generator.planner import plan_from_figma_root
from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.generator.dart.project_validation import validate_dart_project
from figma_flutter_agent.generator.writing.core import DartWriter
from figma_flutter_agent.validation.spec23 import evaluate_spec23

_FIXTURES_DIR = Path("tests/fixtures")
_SKELETON = Path(__file__).parent / "fixtures" / "flutter_skeleton"

_DEMO_FIXTURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("figma_node_sample.json", ()),
    ("figma_carousel_sample.json", ("RepaintBoundary", "PageView")),
    ("figma_tabs_sample.json", ("DefaultTabController", "RepaintBoundary")),
    (
        "figma_bottom_nav_sample.json",
        ("_LayoutChromeNav", "NavigationRail(", "setState(() => _currentIndex = index)"),
    ),
    ("figma_grid_sample.json", ("GridView.count", "RepaintBoundary")),
)


@pytest.mark.parametrize(("fixture_name", "layout_snippets"), _DEMO_FIXTURES)
def test_demo_fixture_passes_spec23_and_layout_contract(
    fixture_name: str,
    layout_snippets: tuple[str, ...],
) -> None:
    """Each demo fixture must pass strict §23 and emit expected layout widgets."""
    root = json.loads((_FIXTURES_DIR / fixture_name).read_text(encoding="utf-8"))
    report = evaluate_spec23(root, Settings(), node_id=root["id"], strict=True)
    assert report.passed, _format_failed(report)

    planned = plan_from_figma_root(root, Settings(), node_id=root["id"], package_name="demo_app")
    layout_files = {
        path: content for path, content in planned.items() if path.endswith("_layout.dart")
    }
    assert layout_files, f"No layout file planned for {fixture_name}"
    layout_source = "\n".join(layout_files.values())
    for snippet in layout_snippets:
        assert snippet in layout_source, f"{fixture_name} missing {snippet!r} in layout"


@pytest.mark.skipif(shutil.which("dart") is None, reason="dart SDK not installed")
def test_demo_node_sample_passes_dart_analyze(tmp_path: Path) -> None:
    """Primary onboarding fixture writes into a skeleton app and passes dart/flutter analyze."""
    root = json.loads((_FIXTURES_DIR / "figma_node_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, Settings(), node_id=root["id"], package_name="demo_app")

    project_dir = tmp_path / "demo_app"
    shutil.copytree(_SKELETON, project_dir)

    writer = DartWriter(project_dir, enable_backup=False)
    batch = writer.write_files(planned)
    pubspec_batch = update_pubspec(project_dir, ["assets/icons/"], needs_svg=False)
    validate_dart_project(project_dir)
    writer.commit_batch(batch)
    commit_pubspec_batch(pubspec_batch)

    theme_files = (
        "lib/theme/app_colors.dart",
        "lib/theme/app_spacing.dart",
        "lib/theme/app_theme.dart",
    )
    for relative in theme_files:
        assert (project_dir / relative).is_file()


@pytest.mark.skipif(shutil.which("dart") is None, reason="dart SDK not installed")
def test_demo_custom_code_preserved_on_regen(tmp_path: Path) -> None:
    """Second generation must keep user edits inside custom-code zones."""
    root = json.loads((_FIXTURES_DIR / "figma_bottom_nav_sample.json").read_text(encoding="utf-8"))
    settings = Settings()
    project_dir = tmp_path / "demo_app"
    shutil.copytree(_SKELETON, project_dir)

    writer = DartWriter(project_dir, enable_backup=False)
    planned = plan_from_figma_root(root, settings, node_id=root["id"], package_name="demo_app")
    writer.commit_batch(writer.write_files(planned))

    layout_path = project_dir / "lib/generated/shell_screen_layout.dart"
    assert layout_path.is_file()
    marker = "debugPrint('demo-signoff-kept');"
    original = layout_path.read_text(encoding="utf-8")
    updated = re.sub(
        r"(// <custom-code:bottom-nav>\s*)",
        rf"\1{marker}\n          ",
        original,
        count=1,
    )
    layout_path.write_text(updated, encoding="utf-8")

    planned_again = plan_from_figma_root(
        root, settings, node_id=root["id"], package_name="demo_app"
    )
    writer.commit_batch(writer.write_files(planned_again))

    assert marker in layout_path.read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("dart") is None, reason="dart SDK not installed")
def test_spec23_dart_analyze_profile_passes_onboarding_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release profile runs flutter analyze on planned output."""
    from figma_flutter_agent.generator import validation

    root = json.loads((_FIXTURES_DIR / "figma_node_sample.json").read_text(encoding="utf-8"))
    planned = plan_from_figma_root(root, Settings(), node_id=root["id"], package_name="demo_app")
    monkeypatch.setattr(validation, "DART_ANALYZE_TIMEOUT_SEC", 240.0)
    ok, detail = validation.validate_planned_dart_files(
        planned,
        require_dart_sdk=True,
    )
    assert ok, detail


def _format_failed(report: object) -> str:
    from figma_flutter_agent.validation.spec23 import Spec23Report

    assert isinstance(report, Spec23Report)
    failed = [item for item in report.criteria if not item.passed]
    return "; ".join(f"{item.name}: {item.detail}" for item in failed)

"""Golden harness Dart: UIGeometryMapper template sync."""

from __future__ import annotations

from pathlib import Path


def test_harness_template_matches_skeleton_fixture() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    template = (
        repo_root / "src/figma_flutter_agent/generator/templates/element_coordinate_mapper.harness"
    )
    fixture = (
        repo_root / "tests/fixtures/flutter_skeleton/test/harness/element_coordinate_mapper.dart"
    )
    assert template.read_text(encoding="utf-8") == fixture.read_text(encoding="utf-8")


def test_harness_exports_geometry_mapper_api() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    harness = (
        repo_root / "src/figma_flutter_agent/generator/templates/element_coordinate_mapper.harness"
    ).read_text(encoding="utf-8")
    assert "class UIGeometryMapper" in harness
    assert "scrollContentBias" in harness
    assert "collectFigmaKeyBounds" in harness
    assert "FrameBounds" in harness

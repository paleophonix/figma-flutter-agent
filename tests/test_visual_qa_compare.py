"""Pixel diff and visual QA comparison tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from figma_flutter_agent.validation.compare import run_visual_qa
from figma_flutter_agent.validation.pixel.compare import compare_png_files
from figma_flutter_agent.validation.specimens import clear_specimen_cache, load_font_specimens


@pytest.fixture(autouse=True)
def _clear_specimen_cache() -> None:
    clear_specimen_cache()


def _write_png(path: Path, color: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (20, 20), color).save(path)


def test_compare_identical_pngs_passes(tmp_path: Path) -> None:
    left = tmp_path / "a.png"
    right = tmp_path / "b.png"
    _write_png(left, (255, 0, 0, 255))
    _write_png(right, (255, 0, 0, 255))
    result = compare_png_files(left.as_posix(), right.as_posix(), threshold=0.05)
    assert result.passed
    assert result.changed_ratio == 0.0
    assert len(result.diff_bands) == 3


def test_compare_different_pngs_fails(tmp_path: Path) -> None:
    left = tmp_path / "a.png"
    right = tmp_path / "b.png"
    _write_png(left, (255, 0, 0, 255))
    _write_png(right, (0, 255, 0, 255))
    result = compare_png_files(left.as_posix(), right.as_posix(), threshold=0.05)
    assert not result.passed
    assert result.changed_ratio == 1.0


def test_compare_resizes_reference_to_actual(tmp_path: Path) -> None:
    large = tmp_path / "large.png"
    small = tmp_path / "small.png"
    Image.new("RGBA", (40, 40), (10, 20, 30, 255)).save(large)
    Image.new("RGBA", (20, 20), (10, 20, 30, 255)).save(small)
    result = compare_png_files(
        large.as_posix(),
        small.as_posix(),
        threshold=0.05,
        resize_reference=True,
    )
    assert result.passed


def test_font_specimens_registry_loads_table_e() -> None:
    registry = load_font_specimens()
    assert len(registry.specimens) == 10
    assert registry.specimens[0].id == "spec_01_btn"


def test_run_visual_qa_skips_missing_specimens(tmp_path: Path) -> None:
    project = tmp_path / "app"
    ref_dir = project / ".debug" / "reference" / "figma"
    golden_dir = project / "test" / "goldens"
    _write_png(ref_dir / "sign_in_figma.png", (255, 255, 255, 255))
    _write_png(golden_dir / "sign_in_screen.png", (255, 255, 255, 255))
    (ref_dir / "sign_in_figma.json").write_text('{"scale": 2.0}', encoding="utf-8")

    report = run_visual_qa(project, "sign_in", threshold=0.05, include_specimens=True)
    assert report.passed
    assert any(item.name == "sign_in_screen" and not item.skipped for item in report.comparisons)
    assert all(item.name.startswith("spec_") and item.skipped for item in report.comparisons[1:])

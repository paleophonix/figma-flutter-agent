"""Fixture manifest golden baseline paths (AC-1 infrastructure)."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.fixtures.screens_manifest import fixtures_root, load_screens_manifest

_DOCKER_GOLDEN_DIR = fixtures_root() / "golden" / "png" / "docker"


@pytest.mark.parametrize(
    "screen_id",
    ["sign_up_and_sign_in", "reminders", "music_v2", "music_v2_ru_dirty"],
)
def test_docker_golden_baseline_file_when_present(screen_id: str) -> None:
    """When baselines exist, each manifest screen has a docker PNG."""
    manifest = load_screens_manifest()
    entry = next(item for item in manifest.screens if item.id == screen_id)
    golden_path = _DOCKER_GOLDEN_DIR / f"{entry.golden_id}.png"
    if not _DOCKER_GOLDEN_DIR.is_dir():
        pytest.skip("docker golden directory not created yet")
    if not golden_path.is_file():
        pytest.skip(f"baseline not generated yet: {golden_path}")
    assert golden_path.stat().st_size > 100


def test_docker_golden_directory_layout() -> None:
    assert _DOCKER_GOLDEN_DIR.parent.name == "png"
    readme = _DOCKER_GOLDEN_DIR / "README.md"
    assert readme.is_file()

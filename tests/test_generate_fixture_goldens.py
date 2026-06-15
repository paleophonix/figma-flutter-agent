"""Safety guards for fixture golden baseline refresh script."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.fixtures.golden_baseline import (
    can_write_fixture_baseline,
    validate_baseline_write,
)
from figma_flutter_agent.fixtures.screens_manifest import ScreenFixtureEntry, fixtures_root


def test_validate_baseline_write_requires_explicit_flag() -> None:
    docker_dir = fixtures_root() / "golden" / "png" / "docker"
    assert (
        validate_baseline_write(
            update_goldens=False,
            golden_runtime="docker",
            output_dir=docker_dir,
        )
        == "pass --update-goldens to write baseline PNGs"
    )


def test_validate_baseline_write_blocks_host_into_docker_dir() -> None:
    docker_dir = fixtures_root() / "golden" / "png" / "docker"
    error = validate_baseline_write(
        update_goldens=True,
        golden_runtime="host",
        output_dir=docker_dir,
    )
    assert error is not None
    assert "docker" in error


def test_validate_baseline_write_allows_docker_into_docker_dir() -> None:
    docker_dir = fixtures_root() / "golden" / "png" / "docker"
    assert (
        validate_baseline_write(
            update_goldens=True,
            golden_runtime="docker",
            output_dir=docker_dir,
        )
        is None
    )


def test_validate_baseline_write_allows_host_into_host_dir(tmp_path: Path) -> None:
    host_dir = tmp_path / "golden" / "png" / "host"
    assert (
        validate_baseline_write(
            update_goldens=True,
            golden_runtime="host",
            output_dir=host_dir,
        )
        is None
    )


def test_entries_without_golden_id_must_not_target_baseline_write() -> None:
    entry = ScreenFixtureEntry(
        id="deep_nesting",
        layout="layouts/deep_nesting_8x.json",
        feature="deep_nesting",
        corpus_tier="advisory_pixel",
    )
    assert not can_write_fixture_baseline(entry)

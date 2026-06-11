"""Tests for canonical screen fixture manifest."""

from __future__ import annotations

import pytest

from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.fixtures.screens_manifest import (
    fixtures_root,
    load_layout_tree,
    load_screens_manifest,
    manifest_path,
)
from figma_flutter_agent.parser.geometry import find_social_auth_row
from figma_flutter_agent.schemas import NodeType


def test_manifest_loads_and_layout_paths_exist() -> None:
    manifest = load_screens_manifest()
    assert manifest.version == 1
    ids = {entry.id for entry in manifest.screens}
    assert {
        "sign_up_and_sign_in",
        "reminders",
        "music_v2",
        "music_v2_ru_dirty",
    } <= ids
    ac2 = [entry for entry in manifest.screens if entry.ac2]
    assert len(ac2) == 1
    assert ac2[0].id == "music_v2_ru_dirty"


def test_load_layout_tree_by_id() -> None:
    tree = load_layout_tree("reminders")
    assert tree.id == "reminders:root"
    assert tree.type == NodeType.STACK


def test_manifest_missing_layout_raises() -> None:
    root = fixtures_root()
    broken = root / "screens_broken.yaml"
    broken.write_text(
        "version: 1\nscreens:\n  - id: x\n    layout: layouts/missing.json\n"
        "    feature: x\n    golden_id: x\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(FigmaFlutterError, match="Layout fixture missing"):
            load_screens_manifest(broken)
    finally:
        broken.unlink(missing_ok=True)


def test_manifest_path_points_to_repo_fixtures() -> None:
    assert manifest_path().name == "screens.yaml"
    assert manifest_path().parent == fixtures_root()


def test_music_dirty_fixture_has_social_row_detected_by_geometry() -> None:
    tree = load_layout_tree("music_v2_ru_dirty")
    row = find_social_auth_row(tree)
    assert row is not None
    assert row.id == "social-row"
    assert row.type == NodeType.ROW

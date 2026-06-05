"""Project font override tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.fonts.bundle import bundle_fonts_for_tree
from figma_flutter_agent.fonts.context import FontResolutionContext
from figma_flutter_agent.fonts.googlefonts import clear_metadata_cache
from figma_flutter_agent.fonts.overrides import PROJECT_OVERRIDES_FILENAME
from figma_flutter_agent.fonts.registry import clear_registry_cache
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeStyle, NodeType, Sizing


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    clear_registry_cache()
    clear_metadata_cache()


def _custom_font_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1",
        name="Label",
        type=NodeType.TEXT,
        text="Brand",
        style=NodeStyle(font_family="Corp Inter", font_weight="w600", font_size=16.0),
        sizing=Sizing(width=100.0, height=20.0),
    )


def test_project_override_maps_custom_family(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overrides = {
        "version": "1",
        "families": [
            {
                "id": "corp_inter",
                "keys": ["corp inter"],
                "pubspec_family": "Corp Inter",
                "strategy": "google_substitute",
                "gwfh_slug": "inter",
                "profile_id": "google_direct_default",
            }
        ],
    }
    (tmp_path / PROJECT_OVERRIDES_FILENAME).write_text(json.dumps(overrides), encoding="utf-8")
    context = FontResolutionContext.for_project(tmp_path)
    entry = context.lookup("Corp Inter")
    assert entry is not None
    assert entry.gwfh_slug == "inter"
    assert entry.pubspec_family == "Corp Inter"


def test_project_profile_override_changes_dart_weight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overrides = {
        "version": "1",
        "family_profiles": {
            "Helvetica Neue": {
                "dart_weight_overrides": {"w500": "w600"},
            }
        },
    }
    (tmp_path / PROJECT_OVERRIDES_FILENAME).write_text(json.dumps(overrides), encoding="utf-8")
    context = FontResolutionContext.for_project(tmp_path)
    profile = context.profile_for_pubspec_family("Helvetica Neue")
    assert profile is not None
    assert profile.dart_weight_override("w500") == "w600"


def test_bundle_uses_disk_cache_without_redownload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIGMA_FLUTTER_FONT_CACHE_DIR", str(tmp_path / "cache"))
    calls: list[str] = []

    def fake_download(url: str, *, client: object) -> bytes:
        calls.append(url)
        return b"cached-font"

    monkeypatch.setattr("figma_flutter_agent.fonts.bundle._download_bytes", fake_download)
    tree = CleanDesignTreeNode(
        id="1",
        name="Label",
        type=NodeType.TEXT,
        text="CONTINUE",
        style=NodeStyle(font_family="Helvetica Neue", font_weight="w500", font_size=14.0),
        sizing=Sizing(width=100.0, height=20.0),
    )
    project = tmp_path / "app"
    project.mkdir()
    bundle_fonts_for_tree(tree, project, download_fonts=True, cache_enabled=True)
    first_call_count = len(calls)
    assert first_call_count > 0
    bundle_fonts_for_tree(tree, project, download_fonts=True, cache_enabled=True)
    assert len(calls) == first_call_count

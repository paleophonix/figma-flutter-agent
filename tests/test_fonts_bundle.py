"""Bundled font export tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.fonts.bundle import bundle_fonts_for_tree
from figma_flutter_agent.fonts.googlefonts import clear_metadata_cache
from figma_flutter_agent.generator.pubspec import commit_pubspec_batch, update_pubspec
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
)


def _helvetica_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="1",
        name="Label",
        type=NodeType.TEXT,
        text="CONTINUE WITH GOOGLE",
        style=NodeStyle(
            font_family="Helvetica Neue",
            font_weight="w500",
            font_size=14.0,
            letter_spacing=0.7,
        ),
        sizing=Sizing(width=200.0, height=20.0),
    )


def _inter_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="2",
        name="Title",
        type=NodeType.TEXT,
        text="Hello",
        style=NodeStyle(
            font_family="Inter",
            font_weight="w600",
            font_size=24.0,
        ),
        sizing=Sizing(width=200.0, height=30.0),
    )


def _google_metadata(family: str, slug: str, *, weight: str, ttf: str) -> dict:
    return {
        "id": slug,
        "family": family,
        "variants": [
            {
                "id": weight,
                "fontStyle": "normal",
                "fontWeight": weight,
                "ttf": ttf,
            }
        ],
    }


@pytest.fixture(autouse=True)
def _clear_google_font_cache() -> None:
    clear_metadata_cache()


def test_bundle_fonts_downloads_helvetica_neue_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_download(url: str, *, client: object) -> bytes:
        assert "inter" in url or "texgyreheros" in url
        return b"regular-font"

    monkeypatch.setattr("figma_flutter_agent.fonts.bundle._download_bytes", fake_download)

    manifest = bundle_fonts_for_tree(_helvetica_tree(), tmp_path)

    assert manifest.bundled_family_names == ["Helvetica Neue"]
    assert (tmp_path / "fonts" / "helvetica_neue_500.ttf").exists()
    assert manifest.families[0].fonts[0].weight == 500


def test_bundle_fonts_downloads_google_font_for_inter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.fonts.googlefonts.fetch_google_font_metadata",
        lambda slug, client=None: (
            _google_metadata(
                "Inter",
                "inter",
                weight="600",
                ttf="https://fonts.gstatic.com/inter-600.ttf",
            )
            if slug == "inter"
            else None
        ),
    )

    def fake_download(url: str, *, client: object) -> bytes:
        assert url.endswith("inter-600.ttf")
        return b"inter-font"

    monkeypatch.setattr("figma_flutter_agent.fonts.bundle._download_bytes", fake_download)

    manifest = bundle_fonts_for_tree(_inter_tree(), tmp_path)

    assert manifest.bundled_family_names == ["Inter"]
    assert (tmp_path / "fonts" / "inter_600.ttf").exists()
    assert manifest.family_aliases["Inter"] == "Inter"


def test_bundle_fonts_maps_arial_to_arimo_under_arial_family(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tree = CleanDesignTreeNode(
        id="3",
        name="Body",
        type=NodeType.TEXT,
        text="Text",
        style=NodeStyle(font_family="Arial", font_weight="w400", font_size=16.0),
        sizing=Sizing(width=100.0, height=20.0),
    )
    monkeypatch.setattr(
        "figma_flutter_agent.fonts.googlefonts.fetch_google_font_metadata",
        lambda slug, client=None: (
            _google_metadata(
                "Arimo",
                "arimo",
                weight="400",
                ttf="https://fonts.gstatic.com/arimo-400.ttf",
            )
            if slug == "arimo"
            else None
        ),
    )
    monkeypatch.setattr(
        "figma_flutter_agent.fonts.bundle._download_bytes",
        lambda url, *, client: b"arimo-font",
    )

    manifest = bundle_fonts_for_tree(tree, tmp_path)

    assert manifest.bundled_family_names == ["Arial"]
    assert manifest.family_aliases["Arial"] == "Arial"
    assert (tmp_path / "fonts" / "arial_400.ttf").exists()


def test_update_pubspec_merges_font_families(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "name: demo_app\n"
        "dependencies:\n"
        "  flutter:\n"
        "    sdk: flutter\n"
        "flutter:\n"
        "  uses-material-design: true\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "figma_flutter_agent.fonts.bundle._download_bytes",
        lambda url, *, client: b"regular-font",
    )
    tree = _helvetica_tree()
    manifest = bundle_fonts_for_tree(tree, tmp_path)
    batch = update_pubspec(tmp_path, ["fonts/"], font_manifest=manifest)
    commit_pubspec_batch(batch)
    content = pubspec.read_text(encoding="utf-8")
    assert "fonts:" in content
    assert "Helvetica Neue" in content
    assert "fonts/helvetica_neue_500.ttf" in content

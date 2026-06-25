"""Bundled font export tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.fonts.bundle import bundle_fonts_for_tree
from figma_flutter_agent.fonts.cache import clear_font_cache
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


from tests.font_bytes import minimal_ttf_payload as _minimal_ttf_payload


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
def _clear_font_caches() -> None:
    clear_metadata_cache()
    clear_font_cache()


def test_bundle_fonts_downloads_helvetica_neue_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_download(url: str, *, client: object) -> bytes:
        assert "inter" in url or "texgyreheros" in url
        return _minimal_ttf_payload()

    monkeypatch.setattr("figma_flutter_agent.fonts.bundle._download_bytes", fake_download)

    manifest = bundle_fonts_for_tree(_helvetica_tree(), tmp_path, download_fonts=True)

    assert manifest.bundled_family_names == ["Helvetica Neue"]
    assert (tmp_path / "assets" / "fonts" / "helvetica_neue_500_analog.ttf").exists()
    assert manifest.families[0].fonts[0].weight == 500
    assert any("analog" in w.lower() for w in manifest.warnings)


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
        return _minimal_ttf_payload()

    monkeypatch.setattr("figma_flutter_agent.fonts.bundle._download_bytes", fake_download)

    manifest = bundle_fonts_for_tree(_inter_tree(), tmp_path, download_fonts=True)

    assert manifest.bundled_family_names == ["Inter"]
    assert (tmp_path / "assets" / "fonts" / "inter_600_analog.ttf").exists()
    assert manifest.family_aliases["Inter"] == "Inter"
    assert any("analog" in w.lower() for w in manifest.warnings)


def _plus_jakarta_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(
                id="a",
                name="Or",
                type=NodeType.TEXT,
                text="Or",
                style=NodeStyle(
                    font_family="Plus Jakarta Sans",
                    font_weight="w400",
                    font_size=12.0,
                ),
                sizing=Sizing(width=20.0, height=16.0),
            ),
            CleanDesignTreeNode(
                id="b",
                name="Google",
                type=NodeType.TEXT,
                text="Continue with Google",
                style=NodeStyle(
                    font_family="Plus Jakarta Sans",
                    font_weight="w600",
                    font_size=14.0,
                ),
                sizing=Sizing(width=200.0, height=20.0),
            ),
            CleanDesignTreeNode(
                id="c",
                name="Headline",
                type=NodeType.TEXT,
                text="Title",
                style=NodeStyle(
                    font_family="Plus Jakarta Sans",
                    font_weight="w700",
                    font_size=32.0,
                ),
                sizing=Sizing(width=200.0, height=40.0),
            ),
        ],
    )


def test_bundle_fonts_downloads_plus_jakarta_weight_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_download(url: str, *, client: object) -> bytes:
        assert "plusjakartasans" in url
        return _minimal_ttf_payload()

    monkeypatch.setattr("figma_flutter_agent.fonts.bundle._download_bytes", fake_download)

    manifest = bundle_fonts_for_tree(_plus_jakarta_tree(), tmp_path, download_fonts=True)

    jakarta = next(item for item in manifest.families if item.family == "Plus Jakarta Sans")
    weights = {font.weight for font in jakarta.fonts}
    assert weights >= {400, 600, 700}
    assert (tmp_path / "assets" / "fonts" / "plus_jakarta_sans_600_analog.ttf").exists()


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
        lambda url, *, client: _minimal_ttf_payload(),
    )

    manifest = bundle_fonts_for_tree(tree, tmp_path, download_fonts=True)

    assert manifest.bundled_family_names == ["Arial"]
    assert manifest.family_aliases["Arial"] == "Arial"
    assert (tmp_path / "assets" / "fonts" / "arial_400_analog.ttf").exists()


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
        lambda url, *, client: _minimal_ttf_payload(),
    )
    tree = _helvetica_tree()
    manifest = bundle_fonts_for_tree(tree, tmp_path, download_fonts=True)
    batch = update_pubspec(tmp_path, ["assets/icons/"], font_manifest=manifest)
    commit_pubspec_batch(batch)
    content = pubspec.read_text(encoding="utf-8")
    assert "fonts:" in content
    assert "Helvetica Neue" in content
    assert "assets/fonts/helvetica_neue_500_analog.ttf" in content

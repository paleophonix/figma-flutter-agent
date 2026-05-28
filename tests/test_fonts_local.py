"""Local project assets/fonts/ discovery and download_fonts policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.fonts.bundle import bundle_font_faces
from figma_flutter_agent.fonts.googlefonts import clear_metadata_cache
from figma_flutter_agent.fonts.local import (
    classify_local_font_match,
    expected_analog_asset_name,
    find_local_analog_font_file,
    find_local_font_file,
    find_local_original_font_file,
)
from figma_flutter_agent.fonts.paths import is_valid_font_bytes
from figma_flutter_agent.schemas import FontFaceRequirement


def _minimal_ttf_payload() -> bytes:
    return b"\x00\x01\x00\x00" + (b"\x00" * 252)


@pytest.fixture(autouse=True)
def _clear_google_font_cache() -> None:
    clear_metadata_cache()


def test_is_valid_font_bytes_rejects_placeholders() -> None:
    assert not is_valid_font_bytes(b"regular-font")
    assert is_valid_font_bytes(_minimal_ttf_payload())


def test_find_local_font_file_exact_name(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    target = fonts_dir / "brand_sans_500.ttf"
    target.write_bytes(_minimal_ttf_payload())

    face = FontFaceRequirement(figma_family="Brand Sans", font_weight="w500")
    found = find_local_font_file(face, tmp_path, pubspec_family="Brand Sans")
    assert found == target


def test_bundle_skips_registry_download_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    face = FontFaceRequirement(figma_family="Helvetica Neue", font_weight="w500")

    def fail_download(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("download must not run when download_fonts is false")

    monkeypatch.setattr("figma_flutter_agent.fonts.bundle._download_bytes", fail_download)
    manifest = bundle_font_faces([face], tmp_path, download_fonts=False, phase="run")
    assert not (tmp_path / "assets" / "fonts" / "helvetica_neue_500_analog.ttf").exists()
    assert any("Substitute available" in w for w in manifest.warnings)


def test_bundle_uses_local_without_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "custom_face_400.ttf").write_bytes(_minimal_ttf_payload())

    def fail_download(*_args: object, **_kwargs: object) -> bytes:
        msg = "download should not run when local file exists"
        raise AssertionError(msg)

    monkeypatch.setattr("figma_flutter_agent.fonts.bundle._download_bytes", fail_download)

    face = FontFaceRequirement(figma_family="Custom Face", font_weight="w400")
    manifest = bundle_font_faces([face], tmp_path, phase="fetch")

    assert manifest.families
    assert (fonts_dir / "custom_face_400.ttf").exists()


def test_bundle_download_fonts_disabled_warns_without_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.fonts.googlefonts.fetch_google_font_metadata",
        lambda slug, client=None: {
            "id": slug,
            "family": "Inter",
            "variants": [
                {
                    "id": "400",
                    "fontStyle": "normal",
                    "fontWeight": "400",
                    "ttf": "https://fonts.gstatic.com/inter-400.ttf",
                }
            ],
        },
    )

    face = FontFaceRequirement(figma_family="Inter", font_weight="w400")
    manifest = bundle_font_faces(
        [face],
        tmp_path,
        download_fonts=False,
        phase="fetch",
    )

    assert not manifest.families
    assert any("assets/fonts/" in warning for warning in manifest.warnings)
    assert any("download_fonts" in warning for warning in manifest.warnings)
    assert any(
        "substitute available" in warning.lower() or "place the original" in warning.lower()
        for warning in manifest.warnings
    )


def test_find_local_prefers_original_over_analog(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    original = fonts_dir / "brand_sans_500.ttf"
    analog = fonts_dir / "brand_sans_500_analog.ttf"
    original.write_bytes(_minimal_ttf_payload())
    analog.write_bytes(_minimal_ttf_payload())

    face = FontFaceRequirement(figma_family="Brand Sans", font_weight="w500")
    assert find_local_original_font_file(face, tmp_path, pubspec_family="Brand Sans") == original
    assert find_local_font_file(face, tmp_path, pubspec_family="Brand Sans") == original
    assert classify_local_font_match(face, tmp_path, pubspec_family="Brand Sans").kind == "exact"


def test_find_local_analog_when_original_missing(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    analog = fonts_dir / expected_analog_asset_name("Brand Sans", 500, None, ext=".ttf")
    analog.write_bytes(_minimal_ttf_payload())

    face = FontFaceRequirement(figma_family="Brand Sans", font_weight="w500")
    assert find_local_original_font_file(face, tmp_path, pubspec_family="Brand Sans") is None
    assert find_local_analog_font_file(face, tmp_path, pubspec_family="Brand Sans") == analog
    assert find_local_font_file(face, tmp_path, pubspec_family="Brand Sans") == analog
    assert classify_local_font_match(face, tmp_path, pubspec_family="Brand Sans").kind == "analog"

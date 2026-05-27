"""Font registry loader and normalization tests."""

from __future__ import annotations

from figma_flutter_agent.fonts.registry import (
    clear_registry_cache,
    load_font_registry,
    normalize_figma_family_key,
)
from figma_flutter_agent.fonts.sources import (
    bundled_package_for_family,
    normalize_figma_family,
    pubspec_family_for_google_alias,
)


def setup_function() -> None:
    clear_registry_cache()


def test_registry_loads_p0_families() -> None:
    registry = load_font_registry()
    assert len(registry.families) >= 90
    assert registry.lookup("Helvetica Neue") is not None
    assert registry.lookup("SF Pro Text") is not None


def test_normalization_strips_apple_dot_and_mt_suffix() -> None:
    assert normalize_figma_family_key(".SF Pro Text") == "sf pro text"
    assert normalize_figma_family_key("Arial MT") == "arial"


def test_normalize_figma_family_maps_helvetica_aliases() -> None:
    assert normalize_figma_family("HelveticaNeue") == "Helvetica Neue"
    assert normalize_figma_family("SF Pro Text") == "SF Pro Text"


def test_bundled_package_uses_profile_for_medium_weight() -> None:
    package = bundled_package_for_family("Helvetica Neue")
    assert package is not None
    medium = package.weight_files["w500"]
    assert medium.weight == 500
    assert "inter" in medium.download_url.lower() or "gstatic" in medium.download_url.lower()


def test_google_alias_returns_registry_pubspec_family() -> None:
    assert pubspec_family_for_google_alias("Arial", "Arimo") == "Arial"
    assert pubspec_family_for_google_alias("Proxima Nova", "Figtree") == "Proxima Nova"


def test_sf_pro_display_uses_inter_tight_slug() -> None:
    registry = load_font_registry()
    entry = registry.lookup("SF Pro Display")
    assert entry is not None
    assert entry.gwfh_slug == "inter-tight"

"""Package fidelity manifest loader tests."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.ir.fidelity_manifest import (
    default_fidelity_manifest,
    load_fidelity_manifest,
    package_fidelity_manifest_path,
)
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind


def test_default_manifest_lives_in_package_not_tests() -> None:
    path = package_fidelity_manifest_path()
    assert path.is_file()
    assert "tests" not in path.parts
    assert path.name == "fidelity_manifest.yaml"


def test_load_fidelity_manifest_import_without_pyyaml() -> None:
    manifest = load_fidelity_manifest()
    assert manifest.tier_for_kind(WidgetIrKind.BUTTON_FILLED) == FidelityTier.NATIVE_VERIFIED
    assert manifest.tier_for_kind(WidgetIrKind.OVERLAY_DIALOG) == FidelityTier.NATIVE_UNVERIFIED


def test_default_fidelity_manifest_cached_loader() -> None:
    manifest = default_fidelity_manifest()
    assert WidgetIrKind.CHIP_CHOICE in manifest.kinds
    assert manifest.kinds[WidgetIrKind.CHIP_CHOICE].fixture_ids == ("chip-row",)


def test_fixture_override_path_still_supported() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[0]
        / "fixtures"
        / "semantics"
        / "fidelity_manifest.yaml"
    )
    assert fixture_path.is_file()
    manifest = load_fidelity_manifest(fixture_path)
    assert manifest.tier_for_kind(WidgetIrKind.BUTTON_FILLED) == FidelityTier.NATIVE_VERIFIED

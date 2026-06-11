"""Composite fidelity manifest lookup (EPIC 4.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.generator.ir.fidelity.manifest import (
    FidelityManifest,
    ManifestEntry,
    load_fidelity_manifest,
)
from figma_flutter_agent.schemas import FidelityTier, TierSource, WidgetIrKind


def test_exact_profile_and_version_match() -> None:
    manifest = FidelityManifest(
        default_tier=FidelityTier.NATIVE_UNVERIFIED,
        template_version="1",
        entries=(
            ManifestEntry(
                kind=WidgetIrKind.BUTTON_FILLED,
                feature_profile="material",
                template_version="1",
                default_tier=FidelityTier.NATIVE_VERIFIED,
                fixture_ids=("btn-filled",),
            ),
        ),
        kinds={},
    )
    resolved = manifest.resolve(
        WidgetIrKind.BUTTON_FILLED,
        feature_profile="material",
        template_version="1",
    )
    assert resolved.tier == FidelityTier.NATIVE_VERIFIED
    assert resolved.tier_source == TierSource.MANIFEST


def test_profile_fallback_to_wildcard_version() -> None:
    manifest = FidelityManifest(
        default_tier=FidelityTier.NATIVE_UNVERIFIED,
        template_version="2",
        entries=(
            ManifestEntry(
                kind=WidgetIrKind.BUTTON_FILLED,
                feature_profile="material",
                template_version="*",
                default_tier=FidelityTier.STYLED_PRIMITIVE,
                fixture_ids=(),
            ),
        ),
        kinds={},
    )
    resolved = manifest.resolve(
        WidgetIrKind.BUTTON_FILLED,
        feature_profile="material",
        template_version="9",
    )
    assert resolved.tier == FidelityTier.STYLED_PRIMITIVE


def test_missing_kind_uses_policy_fallback() -> None:
    manifest = FidelityManifest(
        default_tier=FidelityTier.NATIVE_UNVERIFIED,
        template_version="1",
        entries=(),
        kinds={},
    )
    resolved = manifest.resolve(WidgetIrKind.OVERLAY_DIALOG)
    assert resolved.tier == FidelityTier.NATIVE_UNVERIFIED
    assert resolved.tier_source == TierSource.POLICY_FALLBACK


def test_legacy_kinds_yaml_still_loads() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[0]
        / "fixtures"
        / "semantics"
        / "fidelity_manifest.yaml"
    )
    manifest = load_fidelity_manifest(fixture_path)
    assert manifest.tier_for_kind(WidgetIrKind.BUTTON_FILLED) == FidelityTier.NATIVE_VERIFIED


def test_strict_gate_rejects_unverified_stamped_node() -> None:
    from figma_flutter_agent.errors import GenerationError
    from figma_flutter_agent.generator.ir.context import IrEmitContext
    from figma_flutter_agent.generator.ir.fidelity import route_by_fidelity_tier
    from figma_flutter_agent.generator.ir.passes.fidelity import stamp_fidelity_tiers
    from figma_flutter_agent.schemas import ScreenIr, WidgetIrNode

    manifest = FidelityManifest(
        default_tier=FidelityTier.NATIVE_UNVERIFIED,
        template_version="1",
        entries=(),
        kinds={},
    )
    ir = WidgetIrNode(figma_id="x", kind=WidgetIrKind.OVERLAY_DIALOG)
    stamped = stamp_fidelity_tiers(ScreenIr(root=ir), manifest=manifest)
    assert stamped.root.tier_source == TierSource.POLICY_FALLBACK
    with pytest.raises(GenerationError, match="strict_fidelity"):
        route_by_fidelity_tier(stamped.root, ctx=IrEmitContext(), strict_fidelity=True)

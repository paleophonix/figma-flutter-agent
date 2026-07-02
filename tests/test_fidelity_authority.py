"""LAW-A1-FIDELITY-AUTHORITY: LLM-authored fidelity fields are not compiler authority."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.expression import emit_widget_expression
from figma_flutter_agent.generator.ir.fidelity_manifest import load_fidelity_manifest
from figma_flutter_agent.generator.ir.passes.fidelity import stamp_fidelity_tiers
from figma_flutter_agent.generator.ir.presence.sanitize import (
    sanitize_screen_ir_fidelity_authority,
    sanitize_screen_ir_llm_drift,
)
from figma_flutter_agent.generator.ir.repair import apply_ir_patch_to_screen
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.schemas import (
    FidelityTier,
    NodeType,
    TierSource,
    WidgetIrKind,
    WidgetIrNode,
)
from tests.support.semantics_trees import filled_button, weekday_chip_row


def _classify_and_stamp(clean):
    ir = default_screen_ir(clean)
    classified, _ = classify_screen_ir(
        ir,
        clean,
        confidence_threshold=0.8,
        grey_zone_min=0.5,
        authoritative_classifier=True,
        llm_gray_zone_enabled=False,
    )
    return stamp_fidelity_tiers(classified, clean_tree=clean)


def test_llm_native_verified_on_unknown_kind_not_authoritative() -> None:
    """LLM self-promotion to native_verified on an unmanifested kind is ignored."""
    clean = filled_button()
    screen_ir = default_screen_ir(clean).model_copy(
        update={
            "root": WidgetIrNode(
                figma_id=clean.id,
                kind=WidgetIrKind.OVERLAY_DIALOG,
                fidelity_tier=FidelityTier.NATIVE_VERIFIED,
            ),
        },
    )
    tiers_stripped, sources_stripped = sanitize_screen_ir_fidelity_authority(screen_ir)
    assert tiers_stripped == 1
    assert sources_stripped == 0

    stamped = stamp_fidelity_tiers(screen_ir, manifest=load_fidelity_manifest())
    assert stamped.root.fidelity_tier == FidelityTier.NATIVE_UNVERIFIED
    assert stamped.root.tier_source == TierSource.POLICY_FALLBACK


def test_llm_manual_override_not_trusted() -> None:
    """LLM tierSource=manual_override does not create trusted authority."""
    clean = filled_button()
    screen_ir = default_screen_ir(clean).model_copy(
        update={
            "root": WidgetIrNode(
                figma_id=clean.id,
                kind=WidgetIrKind.BUTTON_FILLED,
                fidelity_tier=FidelityTier.NATIVE_VERIFIED,
                tier_source=TierSource.MANUAL_OVERRIDE,
            ),
        },
    )
    tiers_stripped, sources_stripped = sanitize_screen_ir_fidelity_authority(screen_ir)
    assert tiers_stripped == 1
    assert sources_stripped == 1

    stamped = stamp_fidelity_tiers(screen_ir, clean_tree=clean)
    assert stamped.root.fidelity_tier == FidelityTier.NATIVE_VERIFIED
    assert stamped.root.tier_source == TierSource.MANIFEST
    assert stamped.root.tier_source != TierSource.MANUAL_OVERRIDE


def test_manifest_promotion_preserved() -> None:
    stamped = _classify_and_stamp(filled_button())
    assert stamped.root.kind == WidgetIrKind.BUTTON_FILLED
    assert stamped.root.fidelity_tier == FidelityTier.NATIVE_VERIFIED
    assert stamped.root.tier_source == TierSource.MANIFEST

    stamped_row = _classify_and_stamp(weekday_chip_row())
    assert stamped_row.root.fidelity_tier == FidelityTier.NATIVE_VERIFIED
    assert stamped_row.root.tier_source == TierSource.MANIFEST


def test_policy_fallback_preserved() -> None:
    manifest = load_fidelity_manifest()
    ir = WidgetIrNode(figma_id="x", kind=WidgetIrKind.OVERLAY_DIALOG, fidelity_tier=None)
    stamped = stamp_fidelity_tiers(
        default_screen_ir(filled_button()).model_copy(update={"root": ir}),
        manifest=manifest,
    )
    assert stamped.root.fidelity_tier == FidelityTier.NATIVE_UNVERIFIED
    assert stamped.root.tier_source == TierSource.POLICY_FALLBACK


def test_repair_replace_subtree_strips_fidelity_authority() -> None:
    """Repair irPatches must not bypass sanitize → stamp manifest authority."""
    clean = filled_button()
    baseline = default_screen_ir(clean)
    classified, _ = classify_screen_ir(baseline, clean)
    patched = apply_ir_patch_to_screen(
        classified,
        figma_id=clean.id,
        replace_subtree=WidgetIrNode(
            figma_id=clean.id,
            kind=WidgetIrKind.OVERLAY_DIALOG,
            fidelity_tier=FidelityTier.NATIVE_VERIFIED,
            tier_source=TierSource.MANUAL_OVERRIDE,
        ),
    )
    sanitize_screen_ir_llm_drift(
        patched,
        clean,
        declared_extracted_widget_names=frozenset(),
    )
    validate_screen_ir(patched, clean, apply_guards=False)
    stamped = stamp_fidelity_tiers(patched, clean_tree=clean)

    assert stamped.root.fidelity_tier == FidelityTier.NATIVE_UNVERIFIED
    assert stamped.root.tier_source == TierSource.POLICY_FALLBACK

    ctx = IrEmitContext(semantic_report_only=False, uses_svg=False, responsive_enabled=False)
    dart = emit_widget_expression(
        stamped.root,
        clean=clean,
        parent_type=NodeType.COLUMN,
        ctx=ctx,
    )
    assert "FilledButton" not in dart
    assert "ElevatedButton" not in dart


def test_sanitize_llm_drift_counts_fidelity_strips() -> None:
    clean = filled_button()
    screen_ir = default_screen_ir(clean).model_copy(
        update={
            "root": WidgetIrNode(
                figma_id=clean.id,
                kind=WidgetIrKind.BUTTON_FILLED,
                fidelity_tier=FidelityTier.NATIVE_VERIFIED,
                tier_source=TierSource.MANUAL_OVERRIDE,
            ),
        },
    )
    summary = sanitize_screen_ir_llm_drift(
        screen_ir,
        clean,
        declared_extracted_widget_names=frozenset(),
    )
    assert summary.fidelity_tiers_stripped == 1
    assert summary.tier_sources_stripped == 1

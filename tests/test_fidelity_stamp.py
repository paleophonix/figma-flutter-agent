"""Fidelity tier stamping from manifest (EPIC 3.3)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.fidelity_manifest import load_fidelity_manifest
from figma_flutter_agent.generator.ir.passes.fidelity import stamp_fidelity_tiers
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind, WidgetIrNode
from tests.support.semantics_trees import filled_button, weekday_chip_row


def _stamp_classified(clean):
    ir = default_screen_ir(clean)
    classified, _ = classify_screen_ir(
        ir,
        clean,
        confidence_threshold=0.8,
        grey_zone_min=0.5,
        authoritative_classifier=True,
        llm_gray_zone_enabled=False,
    )
    return stamp_fidelity_tiers(classified)


def test_manifest_promotes_chip_choice() -> None:
    clean = weekday_chip_row()
    stamped = _stamp_classified(clean)
    row_ir = stamped.root
    assert row_ir.kind == WidgetIrKind.CHIP_CHOICE
    assert row_ir.fidelity_tier == FidelityTier.NATIVE_VERIFIED


def test_manifest_promotes_button_filled() -> None:
    clean = filled_button()
    stamped = _stamp_classified(clean)
    btn = stamped.root
    assert btn.kind == WidgetIrKind.BUTTON_FILLED
    assert btn.fidelity_tier == FidelityTier.NATIVE_VERIFIED


def test_unknown_semantic_kind_defaults_unverified() -> None:
    manifest = load_fidelity_manifest()
    ir = WidgetIrNode(
        figma_id="x",
        kind=WidgetIrKind.OVERLAY_DIALOG,
        fidelity_tier=None,
    )
    stamped = stamp_fidelity_tiers(
        default_screen_ir(filled_button()).model_copy(update={"root": ir}),
        manifest=manifest,
    )
    assert stamped.root.fidelity_tier == FidelityTier.NATIVE_UNVERIFIED


def _walk_semantic_tiers(node: WidgetIrNode) -> list[FidelityTier | None]:
    from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS

    tiers: list[FidelityTier | None] = []
    if node.kind in SEMANTIC_IR_KINDS:
        tiers.append(node.fidelity_tier)
    for child in node.children:
        tiers.extend(_walk_semantic_tiers(child))
    return tiers


def test_corpus_semantic_nodes_carry_tier() -> None:
    for clean in (filled_button(), weekday_chip_row()):
        stamped = _stamp_classified(clean)
        tiers = _walk_semantic_tiers(stamped.root)
        assert tiers
        assert all(tier is not None for tier in tiers)

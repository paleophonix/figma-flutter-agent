"""Stamp per-node fidelity tiers from manifest (EPIC 3.3)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.fidelity_manifest import (
    FidelityManifest,
    default_fidelity_manifest,
)
from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
from figma_flutter_agent.schemas import FidelityTier, ScreenIr, WidgetIrNode


def _stamp_node(
    node: WidgetIrNode,
    *,
    manifest: FidelityManifest,
) -> WidgetIrNode:
    if node.fidelity_tier is not None:
        stamped = node
    elif node.kind in SEMANTIC_IR_KINDS:
        stamped = node.model_copy(
            update={"fidelity_tier": manifest.tier_for_kind(node.kind)},
        )
    else:
        stamped = node
    if not stamped.children:
        return stamped
    return stamped.model_copy(
        update={
            "children": [
                _stamp_node(child, manifest=manifest) for child in stamped.children
            ],
        },
    )


def stamp_fidelity_tiers(
    screen_ir: ScreenIr,
    *,
    manifest: FidelityManifest | None = None,
) -> ScreenIr:
    """Apply manifest default tiers to semantic IR nodes missing ``fidelity_tier``."""
    effective = manifest or default_fidelity_manifest()
    return screen_ir.model_copy(
        update={"root": _stamp_node(screen_ir.root, manifest=effective)},
    )


def downgrade_node_tier(
    node: WidgetIrNode,
    figma_id: str,
    *,
    tier: FidelityTier = FidelityTier.NATIVE_UNVERIFIED,
) -> WidgetIrNode:
    """Downgrade one node's tier while preserving ``kind`` annotation."""
    if node.figma_id == figma_id:
        return node.model_copy(update={"fidelity_tier": tier})
    if not node.children:
        return node
    return node.model_copy(
        update={
            "children": [
                downgrade_node_tier(child, figma_id, tier=tier)
                for child in node.children
            ],
        },
    )

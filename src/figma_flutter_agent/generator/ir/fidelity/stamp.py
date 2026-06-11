"""Stamp per-node fidelity tiers from static manifest (EPIC 4.5)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.fidelity.baked_gate import apply_baked_text_policy_to_tier
from figma_flutter_agent.generator.ir.fidelity.manifest import (
    DEFAULT_FEATURE_PROFILE,
    FidelityManifest,
    default_fidelity_manifest,
)
from figma_flutter_agent.generator.ir.tree import index_clean_tree
from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FidelityTier,
    ScreenIr,
    TierSource,
    WidgetIrNode,
)

_CHECKPOINT = "CP2_fidelity_stamp"
_TRANSFORM = "fidelity_stamp"


def _record_stamp_mutation(
    *,
    node_id: str,
    field: str,
    old: object,
    new: object,
    policy: str | None = None,
) -> None:
    from figma_flutter_agent.debug.provenance import get_provenance_recorder

    recorder = get_provenance_recorder()
    if recorder is None:
        return
    recorder.record_mutation(
        checkpoint=_CHECKPOINT,
        transform=_TRANSFORM,
        node_id=node_id,
        field=field,
        old=old,
        new=new,
        policy=policy,
    )


def _stamp_node(
    node: WidgetIrNode,
    *,
    manifest: FidelityManifest,
    feature_profile: str,
    clean_by_id: dict[str, CleanDesignTreeNode] | None,
    strict_fidelity: bool,
    strict_l10n: bool,
    strict_a11y: bool,
) -> WidgetIrNode:
    if node.kind not in SEMANTIC_IR_KINDS:
        stamped = node
    elif node.fidelity_tier is not None:
        stamped = node
        if node.tier_source is None:
            stamped = node.model_copy(update={"tier_source": TierSource.MANUAL_OVERRIDE})
            _record_stamp_mutation(
                node_id=node.figma_id,
                field="tier_source",
                old=None,
                new=TierSource.MANUAL_OVERRIDE.value,
                policy="manual_override",
            )
    else:
        resolved = manifest.resolve(node.kind, feature_profile=feature_profile)
        clean_node = clean_by_id.get(node.figma_id) if clean_by_id is not None else None
        tier, override_source, _reason = apply_baked_text_policy_to_tier(
            resolved.tier,
            clean=clean_node,
            strict_fidelity=strict_fidelity,
            strict_l10n=strict_l10n,
            strict_a11y=strict_a11y,
        )
        tier_source = override_source or resolved.tier_source
        stamped = node.model_copy(
            update={
                "fidelity_tier": tier,
                "tier_source": tier_source,
            },
        )
        _record_stamp_mutation(
            node_id=node.figma_id,
            field="fidelity_tier",
            old=None,
            new=tier.value,
            policy=tier_source.value,
        )
        _record_stamp_mutation(
            node_id=node.figma_id,
            field="tier_source",
            old=None,
            new=tier_source.value,
            policy=tier_source.value,
        )

    if not stamped.children:
        return stamped
    return stamped.model_copy(
        update={
            "children": [
                _stamp_node(
                    child,
                    manifest=manifest,
                    feature_profile=feature_profile,
                    clean_by_id=clean_by_id,
                    strict_fidelity=strict_fidelity,
                    strict_l10n=strict_l10n,
                    strict_a11y=strict_a11y,
                )
                for child in stamped.children
            ],
        },
    )


def stamp_fidelity_tiers(
    screen_ir: ScreenIr,
    *,
    manifest: FidelityManifest | None = None,
    feature_profile: str = DEFAULT_FEATURE_PROFILE,
    clean_tree: CleanDesignTreeNode | None = None,
    strict_fidelity: bool = False,
    strict_l10n: bool = False,
    strict_a11y: bool = False,
) -> ScreenIr:
    """Apply manifest tiers to semantic IR nodes missing ``fidelity_tier``."""
    effective = manifest or default_fidelity_manifest()
    clean_by_id = index_clean_tree(clean_tree) if clean_tree is not None else None
    return screen_ir.model_copy(
        update={
            "root": _stamp_node(
                screen_ir.root,
                manifest=effective,
                feature_profile=feature_profile,
                clean_by_id=clean_by_id,
                strict_fidelity=strict_fidelity,
                strict_l10n=strict_l10n,
                strict_a11y=strict_a11y,
            ),
        },
    )


def downgrade_node_tier(
    node: WidgetIrNode,
    figma_id: str,
    *,
    tier: FidelityTier = FidelityTier.NATIVE_UNVERIFIED,
    tier_source: TierSource = TierSource.POLICY_FALLBACK,
) -> WidgetIrNode:
    """Downgrade one node's tier while preserving ``kind`` annotation."""
    if node.figma_id == figma_id:
        return node.model_copy(update={"fidelity_tier": tier, "tier_source": tier_source})
    if not node.children:
        return node
    return node.model_copy(
        update={
            "children": [
                downgrade_node_tier(child, figma_id, tier=tier, tier_source=tier_source)
                for child in node.children
            ],
        },
    )

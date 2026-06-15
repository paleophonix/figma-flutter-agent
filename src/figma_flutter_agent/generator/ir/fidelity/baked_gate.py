"""Baked-tier emit gating with text policy and shadow records (EPIC 4.5)."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.fidelity.report import (
    FidelityShadowReport,
    shadow_entry_for_baked_downgrade,
)
from figma_flutter_agent.generator.ir.fidelity.router import EmitPath, FidelityRoutePolicy
from figma_flutter_agent.generator.ir.fidelity.text_policy import (
    baked_tier_allowed_for_policy,
    classify_subtree_text_policy,
    primary_text_label,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, FidelityTier, TierSource, WidgetIrNode

_BAKED_TIERS = frozenset({FidelityTier.SVG_BAKED, FidelityTier.PNG_BAKED})


@dataclass(frozen=True)
class BakedEmitDecision:
    """Resolved baked-tier emit outcome."""

    emit_path: EmitPath
    shadow_reason: str | None = None


def apply_baked_text_policy_to_tier(
    tier: FidelityTier,
    *,
    clean: CleanDesignTreeNode | None,
    strict_fidelity: bool = False,
    strict_l10n: bool = False,
    strict_a11y: bool = False,
) -> tuple[FidelityTier, TierSource | None, str | None]:
    """Downgrade baked tiers blocked by text policy during stamping."""
    if tier not in _BAKED_TIERS or clean is None:
        return tier, None, None
    text_policy = classify_subtree_text_policy(clean)
    allowed = baked_tier_allowed_for_policy(
        text_policy,
        strict_fidelity=strict_fidelity,
        strict_l10n=strict_l10n,
        strict_a11y=strict_a11y,
    )
    if allowed:
        return tier, None, None
    reason = f"baked tier blocked by text policy {text_policy.value}"
    return FidelityTier.STYLED_PRIMITIVE, TierSource.POLICY_FALLBACK, reason


def evaluate_baked_emit(
    ir: WidgetIrNode,
    *,
    clean: CleanDesignTreeNode,
    policy: FidelityRoutePolicy,
    report: FidelityShadowReport | None = None,
) -> BakedEmitDecision:
    """Resolve baked emit path with profile-aware text policy."""
    text_policy = classify_subtree_text_policy(clean)
    allowed = baked_tier_allowed_for_policy(
        text_policy,
        strict_fidelity=policy.strict_fidelity,
        strict_l10n=policy.strict_l10n,
        strict_a11y=policy.strict_a11y,
    )
    if allowed:
        return BakedEmitDecision(emit_path=EmitPath.BAKED_ASSET)

    label = primary_text_label(clean)
    reason = f"baked emit blocked for text policy {text_policy.value}"
    entry = shadow_entry_for_baked_downgrade(
        figma_id=ir.figma_id,
        fidelity_tier=ir.fidelity_tier or FidelityTier.PNG_BAKED,
        tier_source=ir.tier_source,
        text_policy=text_policy,
        semantic_label=label,
        reason=reason,
    )
    if report is not None:
        report.add(entry)

    if policy.strict_fidelity or policy.strict_l10n or policy.strict_a11y:
        raise GenerationError(f"{reason} (figmaId={ir.figma_id!r}, kind={ir.kind.value})")

    logger.warning(
        "Downgrading baked tier to styled_primitive for figmaId={} ({})",
        ir.figma_id,
        reason,
    )
    return BakedEmitDecision(
        emit_path=EmitPath.STYLED_PRIMITIVE,
        shadow_reason=reason,
    )

"""Fidelity and baked fallback shadow reports (EPIC 4.5)."""

from __future__ import annotations

from dataclasses import dataclass, field

from figma_flutter_agent.generator.ir.fidelity.text_policy import TextPolicyClass
from figma_flutter_agent.schemas import FidelityTier, TierSource


@dataclass
class FidelityShadowEntry:
    """Passport for a baked or downgraded semantic subtree."""

    figma_id: str
    fidelity_tier: str
    tier_source: str
    contains_text: bool
    text_policy: str
    semantic_label: str | None
    localization_blocker: bool
    accessibility_status: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "figmaId": self.figma_id,
            "fidelityTier": self.fidelity_tier,
            "tierSource": self.tier_source,
            "containsText": self.contains_text,
            "textPolicy": self.text_policy,
            "semanticLabel": self.semantic_label,
            "localizationBlocker": self.localization_blocker,
            "accessibilityStatus": self.accessibility_status,
            "reason": self.reason,
        }


@dataclass
class FidelityShadowReport:
    """Accumulated fidelity shadow entries for one screen."""

    entries: list[FidelityShadowEntry] = field(default_factory=list)

    def add(self, entry: FidelityShadowEntry) -> None:
        self.entries.append(entry)

    def to_dict(self) -> dict[str, object]:
        return {
            "entries": [item.to_dict() for item in self.entries],
            "entryCount": len(self.entries),
        }


def shadow_entry_for_baked_downgrade(
    *,
    figma_id: str,
    fidelity_tier: FidelityTier,
    tier_source: TierSource | None,
    text_policy: TextPolicyClass,
    semantic_label: str | None,
    reason: str,
) -> FidelityShadowEntry:
    """Build a shadow record when baked fallback is blocked or downgraded."""
    contains_text = text_policy != TextPolicyClass.NONE
    from figma_flutter_agent.generator.ir.fidelity.text_policy import localization_blocker

    accessibility_status = (
        "semantic_shadow_only"
        if contains_text
        else "no_text_inventory"
    )
    return FidelityShadowEntry(
        figma_id=figma_id,
        fidelity_tier=fidelity_tier.value,
        tier_source=(tier_source or TierSource.POLICY_FALLBACK).value,
        contains_text=contains_text,
        text_policy=text_policy.value,
        semantic_label=semantic_label,
        localization_blocker=localization_blocker(text_policy),
        accessibility_status=accessibility_status,
        reason=reason,
    )

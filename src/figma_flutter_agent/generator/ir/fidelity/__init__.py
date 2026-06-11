"""Fidelity tier manifest, stamp, routing, and styled fallback emit (EPIC 4.5)."""

from figma_flutter_agent.generator.ir.fidelity.manifest import (
    DEFAULT_FEATURE_PROFILE,
    FidelityManifest,
    ManifestEntry,
    ResolvedTier,
    default_fidelity_manifest,
    feature_profile_from_theme,
    load_fidelity_manifest,
    package_fidelity_manifest_path,
)
from figma_flutter_agent.generator.ir.fidelity.router import (
    EmitPath,
    FidelityRoutePolicy,
    route_by_fidelity_tier,
    route_with_policy,
    semantic_native_emit_allowed,
    tier_allows_native,
)
from figma_flutter_agent.generator.ir.fidelity.stamp import (
    downgrade_node_tier,
    stamp_fidelity_tiers,
)
from figma_flutter_agent.generator.ir.fidelity.styled_emit import emit_styled_primitive

__all__ = [
    "DEFAULT_FEATURE_PROFILE",
    "EmitPath",
    "FidelityManifest",
    "FidelityRoutePolicy",
    "ManifestEntry",
    "ResolvedTier",
    "default_fidelity_manifest",
    "downgrade_node_tier",
    "emit_styled_primitive",
    "feature_profile_from_theme",
    "load_fidelity_manifest",
    "package_fidelity_manifest_path",
    "route_by_fidelity_tier",
    "route_with_policy",
    "semantic_native_emit_allowed",
    "stamp_fidelity_tiers",
    "tier_allows_native",
]

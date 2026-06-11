"""Backward-compatible facade for fidelity routing (EPIC 4.5)."""

from figma_flutter_agent.generator.ir.fidelity.router import (
    EmitPath,
    FidelityRoutePolicy,
    route_by_fidelity_tier,
    route_with_policy,
    semantic_native_emit_allowed,
    tier_allows_native,
)

__all__ = [
    "EmitPath",
    "FidelityRoutePolicy",
    "route_by_fidelity_tier",
    "route_with_policy",
    "semantic_native_emit_allowed",
    "tier_allows_native",
]

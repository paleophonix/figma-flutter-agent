"""M3 authority gate — all enforce decisions go through ``route_enforce_enabled``."""

from __future__ import annotations

from figma_flutter_agent.compiler.m3_policy import (
    DEFAULT_M3_POLICY,
    M3Policy,
    M3Route,
    M3RouteMode,
    m3_policy_from_env,
)

__all__ = [
    "DEFAULT_M3_POLICY",
    "M3Policy",
    "M3Route",
    "M3RouteMode",
    "m3_policy_from_env",
    "require_m3_authority",
    "route_enforce_enabled",
]


def route_enforce_enabled(feature: M3Route, policy: M3Policy) -> bool:
    """Return True only when M2 closure, global authority, and route ENFORCE align."""
    return (
        policy.m2_closed
        and policy.authority_enabled
        and policy.route_mode(feature) == M3RouteMode.ENFORCE
    )


def require_m3_authority(feature: M3Route, policy: M3Policy = DEFAULT_M3_POLICY) -> None:
    """Raise when enforce attempted without full M2 + route gate."""
    mode = policy.route_mode(feature)
    if mode != M3RouteMode.ENFORCE:
        msg = f"M3 route {feature!r} requires ENFORCE mode (current mode={mode.value})"
        raise RuntimeError(msg)
    if not route_enforce_enabled(feature, policy):
        msg = (
            f"M3 authority switch {feature!r} blocked until M2 closure "
            "(m2-closure-record.md CLOSED + FIGMA_M3_AUTHORITY_ENABLED=1)"
        )
        raise RuntimeError(msg)

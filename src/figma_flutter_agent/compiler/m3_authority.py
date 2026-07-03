"""M3 per-route authority modes — production switches blocked until M2 closure."""

from __future__ import annotations

import os
from enum import StrEnum


class M3RouteMode(StrEnum):
    """Rollout mode for one M3 law family / route."""

    OFF = "off"
    REPORT_ONLY = "report_only"
    SHADOW = "shadow"
    ENFORCE = "enforce"


_ROUTE_ENV: dict[str, str] = {
    "definition_key": "FIGMA_M3_DEFINITION_KEY_MODE",
    "extraction_bijection": "FIGMA_M3_BIJECTION_MODE",
    "geometry_slots": "FIGMA_M3_GEOMETRY_SLOTS_MODE",
}


def _parse_mode(raw: str) -> M3RouteMode:
    value = (raw or "off").strip().lower()
    try:
        return M3RouteMode(value)
    except ValueError:
        return M3RouteMode.OFF


def route_mode(feature: str) -> M3RouteMode:
    """Return configured rollout mode for a named M3 route."""
    env_key = _ROUTE_ENV.get(feature)
    if env_key is None:
        return M3RouteMode.OFF
    return _parse_mode(os.environ.get(env_key, "off"))


def m3_authority_enabled() -> bool:
    """True when any route is in ENFORCE mode (compat shim for shadow lookups)."""
    return any(route_mode(name) == M3RouteMode.ENFORCE for name in _ROUTE_ENV)


def require_m3_authority(feature: str) -> None:
    """Raise when enforce attempted without M2 closure gate for this route."""
    mode = route_mode(feature)
    if mode != M3RouteMode.ENFORCE:
        msg = (
            f"M3 route {feature!r} requires FIGMA_M3_*_MODE=enforce "
            f"(current mode={mode.value})"
        )
        raise RuntimeError(msg)
    if os.environ.get("FIGMA_M3_AUTHORITY_ENABLED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        msg = (
            f"M3 authority switch {feature!r} blocked until M2 closure "
            "(set FIGMA_M3_AUTHORITY_ENABLED=1 after m2-closure-record.md CLOSED)"
        )
        raise RuntimeError(msg)

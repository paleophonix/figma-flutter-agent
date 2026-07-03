"""M3 authority gate — production switches blocked until M2 closure."""

from __future__ import annotations

import os


def m3_authority_enabled() -> bool:
    """Return True when M3 production authority switches are explicitly enabled."""
    return os.environ.get("FIGMA_M3_AUTHORITY_ENABLED", "").strip() in {"1", "true", "yes"}


def require_m3_authority(feature: str) -> None:
    """Raise when authority switch attempted without M2 closure gate."""
    if m3_authority_enabled():
        return
    msg = (
        f"M3 authority switch {feature!r} blocked until M2 closure "
        "(set FIGMA_M3_AUTHORITY_ENABLED=1 after m2-closure-record.md CLOSED)"
    )
    raise RuntimeError(msg)

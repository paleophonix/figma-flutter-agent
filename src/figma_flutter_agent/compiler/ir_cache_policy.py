"""IR cache enforce policy (Program 10 P0-1c)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class IrCachePolicyMode(StrEnum):
    OFF = "off"
    REPORT_ONLY = "report_only"
    SHADOW = "shadow"
    ENFORCE = "enforce"


@dataclass(frozen=True, slots=True)
class IrCachePolicy:
    """Pipeline-bound IR cache compatibility policy."""

    mode: IrCachePolicyMode = IrCachePolicyMode.SHADOW

    def shadow_enabled(self) -> bool:
        return self.mode in {IrCachePolicyMode.SHADOW, IrCachePolicyMode.ENFORCE}

    def enforce_enabled(self) -> bool:
        return self.mode == IrCachePolicyMode.ENFORCE


DEFAULT_IR_CACHE_POLICY = IrCachePolicy()


def ir_cache_policy_at_pipeline_boundary() -> IrCachePolicy:
    """Load IR cache policy once at pipeline boundary (env override)."""
    raw = os.environ.get("FIGMA_IR_CACHE_POLICY", "shadow").strip().lower()
    try:
        mode = IrCachePolicyMode(raw)
    except ValueError:
        mode = IrCachePolicyMode.SHADOW
    return IrCachePolicy(mode=mode)

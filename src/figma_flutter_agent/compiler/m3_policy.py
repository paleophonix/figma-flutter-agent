"""M3 rollout policy — injected at pipeline boundary, not read in compiler hot paths."""

from __future__ import annotations

import os
from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from figma_flutter_agent.compiler.m2_closure import (
    load_m2_closure_record,
    m2_closure_record_is_valid,
)

M3Route = Literal["definition_key", "extraction_bijection", "geometry_slots"]


class M3RouteMode(StrEnum):
    """Rollout mode for one M3 law family / route."""

    OFF = "off"
    REPORT_ONLY = "report_only"
    SHADOW = "shadow"
    ENFORCE = "enforce"


def _parse_mode(raw: str) -> M3RouteMode:
    value = (raw or "off").strip().lower()
    try:
        return M3RouteMode(value)
    except ValueError:
        return M3RouteMode.OFF


@dataclass(frozen=True, slots=True)
class M3Policy:
    """Typed M3 authority policy passed through pipeline context."""

    m2_closed: bool = False
    authority_enabled: bool = False
    definition_key_mode: M3RouteMode = M3RouteMode.SHADOW
    bijection_mode: M3RouteMode = M3RouteMode.SHADOW
    geometry_slots_mode: M3RouteMode = M3RouteMode.OFF

    def route_mode(self, feature: M3Route) -> M3RouteMode:
        """Return rollout mode for a named route."""
        if feature == "definition_key":
            return self.definition_key_mode
        if feature == "extraction_bijection":
            return self.bijection_mode
        if feature == "geometry_slots":
            return self.geometry_slots_mode
        return M3RouteMode.OFF

    def shadow_enabled(self, feature: M3Route) -> bool:
        """Return True when route should run shadow diagnostics."""
        mode = self.route_mode(feature)
        return mode in {M3RouteMode.SHADOW, M3RouteMode.ENFORCE}


DEFAULT_M3_POLICY = M3Policy()

_m3_policy_ctx: ContextVar[M3Policy | None] = ContextVar("figma_m3_policy", default=None)


def bind_m3_policy(policy: M3Policy) -> Token[M3Policy | None]:
    """Bind policy for current pipeline plan scope."""
    return _m3_policy_ctx.set(policy)


def reset_m3_policy(token: Token[M3Policy | None]) -> None:
    """Reset policy binding after plan scope completes."""
    _m3_policy_ctx.reset(token)


def active_m3_policy() -> M3Policy:
    """Return bound pipeline policy or safe default."""
    bound = _m3_policy_ctx.get()
    return bound if bound is not None else DEFAULT_M3_POLICY


def is_m2_closure_closed(*, repo_root: Path | None = None) -> bool:
    """Return True only when closure record is fully valid (not status word alone)."""
    record = load_m2_closure_record(repo_root=repo_root)
    return m2_closure_record_is_valid(record)


def m3_policy_at_pipeline_boundary(*, repo_root: Path | None = None) -> M3Policy:
    """Load policy at pipeline boundary (closure record + env modes)."""
    m2_closed = is_m2_closure_closed(repo_root=repo_root)
    authority_requested = os.environ.get("FIGMA_M3_AUTHORITY_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return M3Policy(
        m2_closed=m2_closed,
        authority_enabled=m2_closed and authority_requested,
        definition_key_mode=_parse_mode(os.environ.get("FIGMA_M3_DEFINITION_KEY_MODE", "shadow")),
        bijection_mode=_parse_mode(os.environ.get("FIGMA_M3_BIJECTION_MODE", "shadow")),
        geometry_slots_mode=_parse_mode(os.environ.get("FIGMA_M3_GEOMETRY_SLOTS_MODE", "off")),
    )


def m3_policy_from_env() -> M3Policy:
    """Alias for pipeline boundary loader."""
    return m3_policy_at_pipeline_boundary()

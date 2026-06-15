"""Render profile and pixel fidelity policy (Track A / A1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from figma_flutter_agent.config.models import AgentYamlConfig


class RenderProfile(StrEnum):
    """High-level emit path selection."""

    SEMANTIC_APP = "semantic_app"
    VISUAL_PIXEL = "visual_pixel"
    HYBRID_REVIEW = "hybrid_review"


@dataclass(frozen=True)
class PixelFidelityPolicy:
    """Compile-time policy for visual-pixel render profile."""

    preserve_raw_geometry: bool = True
    allow_layout_reconcile: bool = False
    allow_ir_guards_mutating_paint: bool = False
    allow_semantic_substitution: bool = False
    non_text_pixel_max: float = 0.0
    text_region_pixel_max: float = 0.0
    channel_tolerance: int = 2
    blocking_text_diff: bool = True


def resolve_render_profile(agent: AgentYamlConfig) -> RenderProfile:
    """Resolve render profile from generation flags."""
    generation = agent.generation
    configured = getattr(generation, "render_profile", RenderProfile.SEMANTIC_APP)
    if isinstance(configured, RenderProfile):
        return configured
    if generation.pixel_fidelity or generation.strict_visual_fidelity:
        return RenderProfile.VISUAL_PIXEL
    return RenderProfile(str(configured))


def pixel_fidelity_policy_for_agent(agent: AgentYamlConfig) -> PixelFidelityPolicy:
    """Build pixel fidelity policy from agent configuration."""
    generation = agent.generation
    profile = resolve_render_profile(agent)
    if profile == RenderProfile.SEMANTIC_APP and not generation.pixel_fidelity:
        return PixelFidelityPolicy(
            preserve_raw_geometry=False,
            allow_layout_reconcile=True,
            allow_ir_guards_mutating_paint=True,
            allow_semantic_substitution=True,
            non_text_pixel_max=0.05,
            text_region_pixel_max=0.15,
            channel_tolerance=16,
            blocking_text_diff=False,
        )
    return PixelFidelityPolicy(
        preserve_raw_geometry=generation.preserve_placement,
        allow_layout_reconcile=not generation.suppress_archetype_compensation,
        allow_ir_guards_mutating_paint=False,
        allow_semantic_substitution=False,
        non_text_pixel_max=0.0,
        text_region_pixel_max=0.0,
        channel_tolerance=2,
        blocking_text_diff=True,
    )

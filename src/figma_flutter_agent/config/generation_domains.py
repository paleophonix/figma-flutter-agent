"""Read-only domain views over flat ``GenerationConfig`` (Track 3 / config split)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.config.models import GenerationConfig


@dataclass(frozen=True)
class LlmRepairRefinePolicy:
    """LLM repair and visual refine knobs."""

    llm_repair_attempts: int
    llm_visual_refine: bool
    golden_capture_timeout_sec: float


@dataclass(frozen=True)
class RuntimeGeometryPolicy:
    """Runtime geometry gate thresholds."""

    runtime_geometry_gate: bool
    runtime_fail_renderflex_overflow: bool
    runtime_geometry_min_iou: float


@dataclass(frozen=True)
class GeometryEmitPolicy:
    """Emit-time geometry and render-safety flags."""

    apply_render_safety_guards: bool
    use_geometry_planner: bool
    strict_geometry_invariants: bool


@dataclass(frozen=True)
class FidelityGenerationPolicy:
    """Pixel fidelity and placement preservation flags."""

    pixel_fidelity: bool
    preserve_placement: bool
    render_profile: str
    suppress_archetype_compensation: bool
    archetype_reconcile: bool


def llm_repair_refine_policy(cfg: GenerationConfig) -> LlmRepairRefinePolicy:
    """Build LLM repair/refine policy view from generation config."""
    return LlmRepairRefinePolicy(
        llm_repair_attempts=cfg.llm_repair_attempts,
        llm_visual_refine=cfg.llm_visual_refine,
        golden_capture_timeout_sec=cfg.golden_capture_timeout_sec,
    )


def runtime_geometry_policy(cfg: GenerationConfig) -> RuntimeGeometryPolicy:
    """Build runtime geometry policy view from generation config."""
    return RuntimeGeometryPolicy(
        runtime_geometry_gate=cfg.runtime_geometry_gate,
        runtime_fail_renderflex_overflow=cfg.runtime_fail_renderflex_overflow,
        runtime_geometry_min_iou=cfg.runtime_geometry_min_iou,
    )


def geometry_emit_policy(cfg: GenerationConfig) -> GeometryEmitPolicy:
    """Build geometry emit policy view from generation config."""
    return GeometryEmitPolicy(
        apply_render_safety_guards=cfg.apply_render_safety_guards,
        use_geometry_planner=cfg.use_geometry_planner,
        strict_geometry_invariants=cfg.strict_geometry_invariants,
    )


def fidelity_generation_policy(cfg: GenerationConfig) -> FidelityGenerationPolicy:
    """Build fidelity generation policy view from generation config."""
    profile = cfg.render_profile
    profile_value = profile.value if hasattr(profile, "value") else str(profile)
    return FidelityGenerationPolicy(
        pixel_fidelity=cfg.pixel_fidelity,
        preserve_placement=cfg.preserve_placement,
        render_profile=profile_value,
        suppress_archetype_compensation=cfg.suppress_archetype_compensation,
        archetype_reconcile=cfg.archetype_reconcile,
    )

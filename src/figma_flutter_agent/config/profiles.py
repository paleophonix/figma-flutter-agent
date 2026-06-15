"""Profile application functions for Settings."""

from __future__ import annotations

from .settings import Settings


def apply_signoff_profile(settings: Settings) -> Settings:
    """Apply CI/demo-signoff gates (spec §23) without full production generate profile."""
    agent = settings.agent
    return settings.model_copy(
        update={
            "agent": agent.model_copy(
                update={
                    "quality": agent.quality.model_copy(
                        update={
                            "enforce_spec9_gates": True,
                            "strict_accessibility_labels": True,
                            "fail_duplicate_clusters": True,
                        }
                    ),
                    "generation": agent.generation.model_copy(
                        update={
                            "runtime_fail_renderflex_overflow": True,
                        }
                    ),
                    "validation": agent.validation.model_copy(
                        update={
                            "require_dart_sdk": True,
                            "spec23_dart_analyze": True,
                            "strict_preservation": True,
                        }
                    ),
                }
            )
        }
    )


def apply_interactive_preview_profile(settings: Settings) -> Settings:
    """Fast wizard preview profile for ``run`` / ``launch`` (Chrome manual review).

    Visual refine stays enabled when configured in ``.ai-figma-flutter.yml``; only
    documents that interactive launch does not block refine by default.
    """
    return settings


def apply_refine_ready_profile(settings: Settings) -> Settings:
    """Enable IoU-first visual refine after baseline render quality is acceptable."""
    agent = settings.agent
    return settings.model_copy(
        update={
            "agent": agent.model_copy(
                update={
                    "generation": agent.generation.model_copy(
                        update={
                            "llm_visual_refine": True,
                            "llm_visual_refine_capture_golden": False,
                            "runtime_geometry_gate": True,
                            "runtime_geometry_use_tier_thresholds": True,
                            "runtime_fail_renderflex_overflow": True,
                            "llm_visual_refine_threshold": 0.05,
                        }
                    ),
                }
            )
        }
    )


def apply_showcase_profile(settings: Settings) -> Settings:
    """Enable optional spec §21–§22 features for demos and reviewer walkthroughs."""
    agent = settings.agent
    return settings.model_copy(
        update={
            "agent": agent.model_copy(
                update={
                    "state_management": agent.state_management.model_copy(
                        update={"type": "riverpod"}
                    ),
                    "dark_mode": agent.dark_mode.model_copy(update={"enabled": True}),
                    "ux": agent.ux.model_copy(
                        update={"suggestions": True, "write_report": True}
                    ),
                    "animations": agent.animations.model_copy(
                        update={"write_manifest": True}
                    ),
                    "routing": agent.routing.model_copy(
                        update={"type": "go_router", "generate_destinations": True}
                    ),
                }
            )
        }
    )


def apply_visual_qa_profile(settings: Settings) -> Settings:
    """Enable visual QA outputs (reference PNG, golden tests, dark theme)."""
    agent = settings.agent
    return settings.model_copy(
        update={
            "agent": agent.model_copy(
                update={
                    "dark_mode": agent.dark_mode.model_copy(update={"enabled": True}),
                    "validation": agent.validation.model_copy(
                        update={
                            "export_figma_reference": True,
                            "generate_golden_test": True,
                            "generate_typography_specimen_test": True,
                            "reference_scale": 2.0,
                            "pixel_diff_threshold": 0.05,
                        }
                    ),
                }
            )
        }
    )


def apply_pixel_perfect_profile(settings: Settings) -> Settings:
    """Alias for production profile: pixel fidelity without silent a11y repairs.

    Sets ``accessibility.auto_fix: false`` so font/contrast mutations are not applied
    before strict gates; use warnings and provenance logs when auto_fix is enabled.
    """
    return apply_production_profile(settings)


def apply_production_profile(settings: Settings) -> Settings:
    """Apply strict quality and validation gates for production / CI (spec §9, §23).

    Enables fail-fast LLM-IR behavior.

    ``strict_contrast`` is evaluated on the parse tree **before** ``accessibility.auto_fix``.
    Production sets ``auto_fix: false`` so WCAG failures are not silently repaired before the gate.
    """
    agent = settings.agent
    return settings.model_copy(
        update={
            "llm_require_strict_json_schema": True,
            "agent": agent.model_copy(
                update={
                    "accessibility": agent.accessibility.model_copy(
                        update={"auto_fix": False}
                    ),
                    "quality": agent.quality.model_copy(
                        update={
                            "enforce_spec9_gates": True,
                            "strict_accessibility_labels": True,
                            "strict_contrast": True,
                            "fail_duplicate_clusters": True,
                        }
                    ),
                    "validation": agent.validation.model_copy(
                        update={
                            "require_dart_sdk": True,
                            "spec23_dart_analyze": True,
                            "strict_preservation": True,
                            "analyze_scope": "all_planned",
                        }
                    ),
                    "generation": agent.generation.model_copy(
                        update={
                            "regen_llm_on_token_change": True,
                            "strict_geometry_invariants": True,
                        }
                    ),
                    "responsive": agent.responsive.model_copy(update={"mode": "responsive"}),
                    "layout": agent.layout.model_copy(
                        update={"avoid_fixed_sizes": True}
                    ),
                    "sync": agent.sync.model_copy(
                        update={"enabled": True, "fail_on_corrupt_snapshot": True}
                    ),
                    "assets": agent.assets.model_copy(
                        update={"strict_render_boundary": True}
                    ),
                    "semantics": agent.semantics.model_copy(
                        update={"strict_fidelity": True}
                    ),
                }
            ),
        }
    )

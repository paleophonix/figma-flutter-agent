"""Repair stage replanning — materialize IR and refresh planned files."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.schemas import FlutterGenerationResponse
from figma_flutter_agent.stages.llm_repair.models import LlmRepairStageRequest


def _materialize_generation_for_replan(
    generation: FlutterGenerationResponse,
    request: LlmRepairStageRequest,
) -> FlutterGenerationResponse:
    has_ir = generation.screen_ir is not None or any(
        widget.widget_ir is not None for widget in generation.extracted_widgets
    )
    if not has_ir:
        return generation
    from figma_flutter_agent.generator.ir.context import IrEmitContext
    from figma_flutter_agent.generator.ir.materialize import materialize_screen_code_from_ir
    from figma_flutter_agent.generator.planner import _resolve_use_scaffold
    from figma_flutter_agent.generator.theme_typography import (
        build_text_theme_size_slots,
        build_text_theme_slot_by_style_name,
    )

    settings = request.settings
    uses_svg = any(
        item.asset_path.lower().endswith(".svg")
        for item in request.asset_manifest.entries
    )
    theme_variant = settings.agent.theme.variant
    semantics = settings.agent.semantics
    return materialize_screen_code_from_ir(
        generation,
        clean_tree=request.clean_tree,
        feature_name=request.resolved_feature,
        ctx=IrEmitContext(
            uses_svg=uses_svg,
            cluster_classes=None,
            cluster_vector_variants=None,
            theme_variant=theme_variant,
            responsive_enabled=settings.agent.responsive.enabled,
            is_layout_root=True,
            bundled_font_families=frozenset(
                request.font_manifest.bundled_family_names
            ),
            dart_weight_overrides_by_family=(
                request.font_manifest.dart_weight_overrides_by_family
            ),
            text_theme_slot_by_style_name=build_text_theme_slot_by_style_name(
                request.tokens
            ),
            text_theme_size_slots=build_text_theme_size_slots(request.tokens),
            strict_fidelity=semantics.strict_fidelity,
            strict_l10n=semantics.strict_l10n,
            strict_a11y=semantics.strict_a11y,
        ),
        use_auto_route=settings.agent.routing.type == "auto_route",
        use_scaffold=_resolve_use_scaffold(settings, request.clean_tree),
        responsive_shell=settings.agent.responsive.enabled,
        project_dir=request.project_dir,
        tokens=request.tokens,
    )


def replan_planned_files(
    request: LlmRepairStageRequest,
    generation: FlutterGenerationResponse,
    *,
    base_planned: dict[str, str] | None = None,
) -> dict[str, str]:
    """Refresh screen + extracted widgets only; keep layout/theme/bootstrap from prior plan."""
    from figma_flutter_agent.generator.renderer import DartRenderer

    materialized = _materialize_generation_for_replan(generation, request)
    merged = dict(base_planned if base_planned is not None else request.planned_files)
    settings = request.settings
    generation_cfg = settings.agent.generation
    uses_svg = any(
        item.asset_path.lower().endswith(".svg")
        for item in request.asset_manifest.entries
    )
    renderer = DartRenderer()
    patch = renderer.render_generation_files(
        materialized,
        feature_name=request.resolved_feature,
        uses_svg=uses_svg,
        use_auto_route=settings.agent.routing.type == "auto_route",
        responsive_enabled=settings.agent.responsive.enabled,
        shell_safe_area=settings.agent.responsive.shell_safe_area,
        max_web_width=settings.agent.responsive.max_web_width,
        layout_import=f"{request.resolved_feature}_layout",
        architecture=settings.agent.flutter.architecture,
        package_name=request.package_name,
        use_package_imports=generation_cfg.use_package_imports,
        state_management_type=settings.agent.state_management.type,
    )
    merged.update(patch)
    logger.info(
        "Repair replan (lightweight): updated {} file(s), retained {} planned path(s)",
        len(patch),
        len(merged),
    )
    return merged

"""LLM visual refine loop for planned Dart files."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from loguru import logger

from figma_flutter_agent.errors import LlmError, format_error_for_log
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files
from figma_flutter_agent.generator.validation import analyze_planned_dart_files
from figma_flutter_agent.llm.client import LlmClient
from figma_flutter_agent.llm.refine_context import (
    RefineAttemptSummary,
    audit_interaction_handlers,
    build_asset_warnings,
    build_canvas_size,
    build_interactive_inventory,
    resolve_refine_focus,
)
from figma_flutter_agent.llm.repair import _serialize_diff_regions
from figma_flutter_agent.observability.llm_trace import set_llm_stage
from figma_flutter_agent.render_log import (
    ensure_render_log_session,
    expected_render_png_path,
    record_render_png,
)
from figma_flutter_agent.stages.llm_repair import (
    LlmRepairStageRequest,
    replan_planned_files,
)
from figma_flutter_agent.validation.compare import compare_png_bytes
from figma_flutter_agent.validation.golden_capture import (
    GoldenCaptureHostSession,
    capture_planned_flutter_golden_png,
)
from figma_flutter_agent.validation.iou import compute_widget_diff_scores, select_surgical_targets
from figma_flutter_agent.validation.pixeldiff import (
    TextCoordinateValidationResult,
    VisualCompareResult,
    parse_flutter_mapper_payload,
    render_visual_diff_heatmap_png,
)
from figma_flutter_agent.validation.reference import REFERENCE_DIR_NAME
from figma_flutter_agent.validation.surgical_refine import build_surgical_snippets


@dataclass
class LlmVisualRefineStageResult:
    """Output of the visual refine loop."""

    planned_files: dict[str, str]
    warnings: list[str] = field(default_factory=list)
    refine_attempts: int = 0
    initial_changed_ratio: float | None = None
    final_changed_ratio: float | None = None


def _should_run_visual_refine(request: LlmRepairStageRequest) -> bool:
    generation_cfg = request.settings.agent.generation
    if request.dry_run:
        return False
    if request.use_deterministic_screen:
        return False
    if not generation_cfg.llm_visual_refine:
        return False
    if request.llm_result.generation is None:
        return False
    return not request.llm_result.skipped_incremental


def _resolve_figma_reference_png(request: LlmRepairStageRequest) -> bytes | None:
    if request.figma_reference_png is not None:
        return request.figma_reference_png
    reference_png = (
        request.project_dir / REFERENCE_DIR_NAME / f"{request.resolved_feature}_figma.png"
    )
    if reference_png.is_file():
        return reference_png.read_bytes()
    return None


def _compare_visual(
    request: LlmRepairStageRequest,
    *,
    figma_png: bytes,
    flutter_png: bytes,
    threshold: float,
    flutter_mapper_payload: dict | None,
) -> VisualCompareResult:
    generation_cfg = request.settings.agent.generation
    outcome = compare_png_bytes(
        figma_png,
        flutter_png,
        threshold=threshold,
        clean_tree=request.clean_tree,
        flutter_mapper=parse_flutter_mapper_payload(flutter_mapper_payload),
        text_coordinate_tolerance=generation_cfg.text_coordinate_tolerance,
    )
    if isinstance(outcome, VisualCompareResult):
        return outcome
    return VisualCompareResult(
        pixel=outcome,
        text_validation=TextCoordinateValidationResult(passed=True),
    )


async def run_visual_refine_loop(
    request: LlmRepairStageRequest,
    *,
    planned_files: dict[str, str],
    llm_client_factory: Callable | None = None,
) -> LlmVisualRefineStageResult:
    """Iteratively refine LLM output when pixel diff exceeds the configured threshold.

    Loop semantics:
        compare тЖТ (fail) тЖТ visual refine LLM тЖТ re-plan тЖТ analyze тЖТ re-capture тЖТ compare
        until diff <= threshold or ``llm_visual_refine_max_attempts`` is exhausted.

    Args:
        request: Pipeline context shared with the analyze repair stage.
        planned_files: Current planned files after analyze repair.
        llm_client_factory: Optional LLM client factory override for tests.

    Returns:
        Updated planned files and visual refine metrics/warnings.
    """
    result = LlmVisualRefineStageResult(planned_files=dict(planned_files))
    log = logger.bind(stage="llm_visual_refine", feature_name=request.resolved_feature)
    if not _should_run_visual_refine(request):
        log.info("Visual refine skipped: disabled or not applicable for this run")
        return result

    generation_cfg = request.settings.agent.generation
    if not generation_cfg.llm_visual_refine_capture_golden:
        message = "Visual refine off: capture_golden disabled"
        result.warnings.append(message)
        log.info(message)
        return result

    figma_png = _resolve_figma_reference_png(request)
    if figma_png is None:
        message = (
            f"Visual refine off: no Figma reference "
            f"({REFERENCE_DIR_NAME}/{request.resolved_feature}_figma.png)"
        )
        result.warnings.append(message)
        log.warning(message)
        return result

    set_llm_stage("refine")
    llm_api_key = request.settings.llm_api_key()
    if not llm_api_key:
        message = "Visual refine off: no LLM API key"
        result.warnings.append(message)
        log.warning(message)
        return result

    render_dir = ensure_render_log_session(
        feature_name=request.resolved_feature,
        project_dir=request.project_dir,
    )
    if render_dir is None:
        log.warning(
            "Combat render log session could not be bound; PNGs will not land under logs/renders/"
        )

    record_render_png("figma_reference", figma_png)

    threshold = generation_cfg.llm_visual_refine_threshold
    max_attempts = generation_cfg.llm_visual_refine_max_attempts
    analyze_scope = request.settings.agent.validation.analyze_scope
    require_dart_sdk = request.settings.agent.validation.require_dart_sdk
    llm_client: LlmClient | None = None
    asset_entries = [entry.model_dump() for entry in request.asset_manifest.entries]

    def _llm_client() -> LlmClient:
        nonlocal llm_client
        if llm_client is not None:
            return llm_client
        if llm_client_factory is not None:
            factory = llm_client_factory
        elif request.llm_refine_client_factory is not None:
            factory = request.llm_refine_client_factory
        elif request.llm_client_factory is not None:
            factory = request.llm_client_factory
        else:
            from figma_flutter_agent.pipeline.deps import default_pipeline_dependencies

            factory = default_pipeline_dependencies().create_llm_refine_client
        llm_client = factory(request.settings)
        return llm_client

    log.info(
        "Using LLM refine model {} (provider={})",
        request.settings.resolved_llm_refine_model(),
        request.settings.resolved_llm_provider(),
    )
    refine_attempts = 0
    previous_changed_ratio: float | None = None
    refine_history: list[RefineAttemptSummary] = []
    excluded_surgical_ids: set[str] = set()
    interactive_inventory = build_interactive_inventory(request.clean_tree)
    canvas_size = build_canvas_size(request.clean_tree)
    asset_warnings = build_asset_warnings(
        clean_tree=request.clean_tree,
        asset_manifest=asset_entries,
    )
    host_session: GoldenCaptureHostSession | None = None

    def _release_capture_session() -> None:
        nonlocal host_session
        if host_session is not None:
            host_session.close()
            host_session = None

    try:
        while True:
            flutter_artifact_attempt = refine_attempts if refine_attempts > 0 else None
            pending_path = expected_render_png_path(
                "flutter_render",
                attempt=flutter_artifact_attempt,
            )
            pending_display = (
                pending_path.resolve().as_posix()
                if pending_path is not None
                else "(logs/renders/<session>/flutter_render.png)"
            )
            log.info(
                "Capturing Flutter screen in {} (fast PNG capture; diff runs in Python). "
                "Target: {}{}",
                request.project_dir,
                pending_display,
                f" (attempt {refine_attempts})" if refine_attempts else "",
            )
            capture = capture_planned_flutter_golden_png(
                result.planned_files,
                feature_name=request.resolved_feature,
                flutter_sdk=request.settings.flutter_sdk or None,
                project_dir=request.project_dir,
                settings=request.settings,
                layout_tree=request.clean_tree,
                host_session=host_session,
            )
            if capture.host_session is not None:
                host_session = capture.host_session
            if not capture.ok:
                reason = capture.reason or "golden capture failed"
                message = f"Visual refine off: {reason}"
                result.warnings.append(message)
                log.warning(
                    "{} (no flutter_render.png — fix analyze/build errors or golden test failure)",
                    message,
                )
                return result
            flutter_png = capture.png
            assert flutter_png is not None
            flutter_mapper_payload = capture.figma_key_rects
            from figma_flutter_agent.validation.runtime_geometry import (
                geometry_feedback_from_mapper_payload,
            )

            generation_cfg = request.settings.agent.generation
            geometry_feedback = geometry_feedback_from_mapper_payload(
                request.clean_tree,
                flutter_mapper_payload,
                min_iou=generation_cfg.runtime_geometry_min_iou,
                tier_thresholds=generation_cfg.geometry_tier_thresholds(),
                use_tier_thresholds=generation_cfg.runtime_geometry_use_tier_thresholds,
            )
            if geometry_feedback:
                log.info("Runtime geometry feedback:\n{}", geometry_feedback)
            saved = record_render_png(
                "flutter_render",
                flutter_png,
                attempt=flutter_artifact_attempt,
                changed_ratio=None,
            )
            log.info(
                "Flutter screen capture ready ({} bytes) at {}",
                len(flutter_png),
                saved or pending_path or "logs/renders",
            )

            compare_outcome = _compare_visual(
                request,
                figma_png=figma_png,
                flutter_png=flutter_png,
                threshold=threshold,
                flutter_mapper_payload=flutter_mapper_payload,
            )
            diff = compare_outcome.pixel
            if result.initial_changed_ratio is None:
                result.initial_changed_ratio = diff.changed_ratio
            result.final_changed_ratio = diff.changed_ratio
            similarity = max(0.0, 1.0 - diff.changed_ratio)
            log.info(
                "Pixel similarity {:.1%} ({:.2%} changed vs Figma, threshold {:.2%})",
                similarity,
                diff.changed_ratio,
                threshold,
            )

            if not compare_outcome.text_validation.passed:
                repair_message = compare_outcome.text_validation.first_repair_message
                message = repair_message or "TEXT coordinate validation failed"
                result.warnings.append(message)
                log.warning("Visual refine stopped: {}", message)
                result.refine_attempts = refine_attempts
                return result

            if compare_outcome.passed:
                if refine_attempts:
                    log.info(
                        "Visual refine succeeded after {} attempt(s); diff {:.2%} <= {:.2%}",
                        refine_attempts,
                        diff.changed_ratio,
                        threshold,
                    )
                else:
                    log.info(
                        "Visual refine skipped: diff {:.2%} already <= {:.2%}",
                        diff.changed_ratio,
                        threshold,
                    )
                return result

            if refine_attempts >= max_attempts:
                result.warnings.append(
                    "LLM visual refine exhausted "
                    f"({refine_attempts}/{max_attempts} attempts); "
                    f"final diff {diff.changed_ratio:.2%} > {threshold:.2%}."
                )
                log.warning(
                    "Visual refine exhausted after {} attempt(s); diff {:.2%} > {:.2%}",
                    refine_attempts,
                    diff.changed_ratio,
                    threshold,
                )
                return result

            refine_attempts += 1
            log.warning(
                "Visual diff above threshold (attempt {}/{}): {:.2%} > {:.2%}",
                refine_attempts,
                max_attempts,
                diff.changed_ratio,
                threshold,
            )
            if request.llm_result.generation is None:
                break

            previous_planned = dict(result.planned_files)
            previous_generation = request.llm_result.generation
            handler_audit = audit_interaction_handlers(
                interactive_inventory,
                request.llm_result.generation,
            )
            refine_focus = resolve_refine_focus(
                attempt=refine_attempts,
                max_attempts=max_attempts,
            )

            heatmap_png = render_visual_diff_heatmap_png(
                figma_png,
                flutter_png,
                clean_tree=request.clean_tree,
            )
            record_render_png(
                "diff_heatmap",
                heatmap_png,
                attempt=refine_attempts,
                changed_ratio=diff.changed_ratio,
            )
            screen_rel = f"lib/features/{request.resolved_feature}/{request.resolved_feature}_screen.dart"
            screen_code = result.planned_files.get(screen_rel, "")
            surgical_snippets: dict[str, str] = {}
            if screen_code:
                widget_scores = compute_widget_diff_scores(
                    figma_png,
                    flutter_png,
                    request.clean_tree,
                )
                target_ids = [
                    node_id
                    for node_id in select_surgical_targets(widget_scores)
                    if node_id not in excluded_surgical_ids
                ]
                if target_ids:
                    surgical_snippets = build_surgical_snippets(screen_code, target_ids)
                    log.bind(
                        surgical_targets=target_ids,
                        snippet_count=len(surgical_snippets),
                    ).info("IoU surgical refine targeting {} widget(s)", len(surgical_snippets))
            try:
                refined = await _llm_client().visual_refine_async(
                    request.clean_tree,
                    request.tokens,
                    feature_name=request.resolved_feature,
                    asset_manifest=asset_entries,
                    current_generation=request.llm_result.generation,
                    changed_ratio=diff.changed_ratio,
                    threshold=threshold,
                    widget_hints=request.widget_hints,
                    navigation_hints=request.navigation_hints,
                    routing_enabled=request.routing_on,
                    theme_variant=request.settings.agent.theme.variant,
                    figma_reference_png=figma_png,
                    flutter_render_png=flutter_png,
                    visual_diff_png=heatmap_png,
                    refine_attempt=refine_attempts,
                    max_refine_attempts=max_attempts,
                    previous_changed_ratio=previous_changed_ratio,
                    refine_focus=refine_focus,
                    diff_bands=diff.diff_bands,
                    refine_history=tuple(refine_history),
                    interactive_inventory=interactive_inventory,
                    handler_audit=handler_audit,
                    canvas_size=canvas_size,
                    asset_warnings=asset_warnings,
                    surgical_widget_snippets=surgical_snippets or None,
                    geometry_feedback=geometry_feedback or None,
                    use_screen_ir=request.settings.agent.generation.use_screen_ir,
                    require_screen_ir=request.settings.agent.generation.require_screen_ir,
                    project_dir=request.project_dir,
                )
            except LlmError as exc:
                refine_history.append(
                    RefineAttemptSummary(
                        attempt=refine_attempts,
                        changed_ratio=diff.changed_ratio,
                        outcome="llm_error",
                        error_preview=format_error_for_log(exc),
                        diff_regions=tuple(_serialize_diff_regions(diff.diff_bands)),
                    )
                )
                result.warnings.append(f"LLM visual refine attempt {refine_attempts} failed: {exc}")
                log.warning(
                    "LLM visual refine attempt {} failed: {}",
                    refine_attempts,
                    format_error_for_log(exc),
                )
                result.refine_attempts = refine_attempts
                return result

            request.llm_result.generation = refined
            result.planned_files = replan_planned_files(request, refined)
            result.planned_files = reconcile_planned_dart_files(
                result.planned_files,
                blocked_asset_paths=request.blocked_asset_paths,
                typography_tokens=request.tokens,
                package_name=request.package_name,
                clean_tree=request.clean_tree,
                incremental=True,
                project_dir=request.project_dir,
                widget_suffix=request.settings.agent.naming.widget_suffix,
                uses_svg=any(item.kind == "icon" for item in request.asset_manifest.entries),
                use_package_imports=request.settings.agent.generation.use_package_imports,
            )
            analyze_outcome = analyze_planned_dart_files(
                result.planned_files,
                package_name=request.package_name,
                require_dart_sdk=require_dart_sdk,
                analyze_scope=analyze_scope,
                analyze_stage="llm_visual_refine",
                analyze_attempt=refine_attempts,
                flutter_sdk=request.settings.flutter_sdk or None,
                skip_planned_reconcile=True,
            )
            if analyze_outcome.skipped:
                log.info("Visual refine analyze skipped: {}", analyze_outcome.detail)
                result.refine_attempts = refine_attempts
                return result
            if not analyze_outcome.passed:
                error_preview = "; ".join(analyze_outcome.errors[:3])
                if surgical_snippets:
                    excluded_surgical_ids.update(surgical_snippets)
                refine_history.append(
                    RefineAttemptSummary(
                        attempt=refine_attempts,
                        changed_ratio=diff.changed_ratio,
                        outcome="analyze_failed",
                        error_preview=error_preview or analyze_outcome.detail,
                        diff_regions=tuple(_serialize_diff_regions(diff.diff_bands)),
                        excluded_surgical_ids=tuple(surgical_snippets.keys()),
                    )
                )
                request.llm_result.generation = previous_generation
                result.planned_files = previous_planned
                result.warnings.append(
                    f"LLM visual refine attempt {refine_attempts} broke dart analyze; "
                    "keeping previous output and continuing refine for other widgets."
                )
                log.warning(
                    "Visual refine attempt {} failed analyze: {} тАФ {}; excluded {} surgical target(s)",
                    refine_attempts,
                    analyze_outcome.detail,
                    error_preview or "(no analyzer lines)",
                    len(surgical_snippets),
                )
                result.refine_attempts = refine_attempts
                continue

            refine_history.append(
                RefineAttemptSummary(
                    attempt=refine_attempts,
                    changed_ratio=diff.changed_ratio,
                    outcome="replanned",
                    diff_regions=tuple(_serialize_diff_regions(diff.diff_bands)),
                )
            )
            result.refine_attempts = refine_attempts
            previous_changed_ratio = diff.changed_ratio
            log.info(
                "LLM visual refine attempt {} complete (focus={}); re-planned and re-capturing golden",
                refine_attempts,
                refine_focus,
            )

    finally:
        _release_capture_session()
    return result

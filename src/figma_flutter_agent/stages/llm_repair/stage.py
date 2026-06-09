"""Repair stage orchestration — public API for LLM analyze repair loop."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import LlmError, LlmRepairStalledError, format_error_for_log
from figma_flutter_agent.generator.planned.reconcile import (
    reconcile_planned_dart_files,
    repair_planned_format_parse_failures,
    repair_planned_misplaced_text_style_params,
)
from figma_flutter_agent.generator.dart.project_validation import (
    analyze_planned_dart_files,
    normalize_analyzer_errors_for_fingerprint,
)
from figma_flutter_agent.generator.paths import screen_file_path
from figma_flutter_agent.llm.clients import LlmClient
from figma_flutter_agent.llm.repair_scope import (
    RepairEnvironmentContext,
    build_repair_environment_context,
    build_repair_scope,
)
from figma_flutter_agent.observability.llm_trace import set_llm_stage
from figma_flutter_agent.parser.prototype import PrototypeNavigationPlan
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    FontManifest,
    ScreenIr,
)
from figma_flutter_agent.stages.llm import LlmStageResult
from figma_flutter_agent.stages.repair_prompt_escalation import RepairPromptEscalator
from figma_flutter_agent.stages.llm_repair.snapshot import (
    _GenerationSnapshot,
    _apply_extracted_widget_reference_fixup,
    _errors_suggest_extracted_widget_drift,
    _repair_generation_unchanged,
    _restore_generation,
    _snapshot_generation,
)
from figma_flutter_agent.stages.llm_repair.syntax import (
    _critical_syntax_broken_directive,
    _format_failure_paths_from_outcome,
    _is_syntax_level_analyze_failure,
    _planned_files_have_delimiter_syntax_errors,
    _repair_patch_has_duplicate_required_this,
    _syntax_error_count,
    _syntax_repair_stalled,
)


@dataclass
class LlmRepairStageRequest:
    """Inputs for post-generation LLM repair and visual refine loops."""

    settings: Settings
    dry_run: bool
    project_dir: Path
    planned_files: dict[str, str]
    llm_result: LlmStageResult
    clean_tree: CleanDesignTreeNode
    tokens: DesignTokens
    resolved_feature: str
    node_id: str
    cluster_summary: dict[str, int]
    asset_manifest: AssetManifest
    font_manifest: FontManifest
    widget_hints: list[str]
    navigation_hints: list[str]
    routing_on: bool
    navigation_plan: PrototypeNavigationPlan
    figma_root: dict[str, Any]
    package_name: str
    blocked_asset_paths: frozenset[str] = field(default_factory=frozenset)
    destination_trees: dict[str, CleanDesignTreeNode] = field(default_factory=dict)
    llm_client_factory: Callable[[Settings], LlmClient] | None = None
    llm_refine_client_factory: Callable[[Settings], LlmClient] | None = None
    figma_reference_png: bytes | None = None


@dataclass
class LlmRepairStageResult:
    """Output of the analyze repair loop."""

    planned_files: dict[str, str]
    llm_result: LlmStageResult
    warnings: list[str] = field(default_factory=list)
    repair_attempts: int = 0


def _rollback_repair_to_baseline(
    result: LlmRepairStageResult,
    *,
    baseline_planned: dict[str, str],
    baseline_generation: _GenerationSnapshot | None,
    log,
    reason: str,
) -> None:
    """Restore planned files and generation to the pre-repair-loop baseline."""
    result.planned_files = dict(baseline_planned)
    if baseline_generation is not None and result.llm_result.generation is not None:
        _restore_generation(result.llm_result.generation, baseline_generation)
    log.warning("Repair exhausted — rolled back to pre-repair baseline ({})", reason)


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


def _should_run_repair(request: LlmRepairStageRequest) -> bool:
    generation_cfg = request.settings.agent.generation
    if request.dry_run:
        return False
    if not generation_cfg.llm_repair_after_analyze:
        return False
    if request.llm_result.generation is None:
        return False
    return not request.llm_result.skipped_incremental


async def run_analyze_repair_loop(request: LlmRepairStageRequest) -> LlmRepairStageResult:
    """Repair LLM output when planned Dart fails analyze in a temp skeleton project.

    Args:
        request: Planned files, LLM output, and pipeline context for re-planning.

    Returns:
        Updated planned files and LLM result after zero or more repair attempts.

    Raises:
        LlmRepairStalledError: When syntax/format errors fail to decrease after repeated repairs.
        LlmError: Not raised otherwise; repair failures are logged and the last planned state is kept.
    """
    result = LlmRepairStageResult(
        planned_files=dict(request.planned_files),
        llm_result=request.llm_result,
    )
    if not _should_run_repair(request):
        return result

    set_llm_stage("repair")
    log = logger.bind(stage="llm_repair", feature_name=request.resolved_feature)
    generation_cfg = request.settings.agent.generation
    analyze_scope = request.settings.agent.validation.analyze_scope
    require_dart_sdk = request.settings.agent.validation.require_dart_sdk
    max_attempts = generation_cfg.llm_repair_max_attempts

    llm_api_key = request.settings.llm_api_key()
    if not llm_api_key:
        result.warnings.append(
            "LLM analyze repair skipped: API key missing while planned Dart failed analyze."
        )
        return result

    if request.llm_client_factory is not None:
        client_factory = request.llm_client_factory
    else:
        from figma_flutter_agent.pipeline.deps import default_pipeline_dependencies

        client_factory = default_pipeline_dependencies().create_llm_repair_client
    llm_client = client_factory(request.settings)
    generate_model = request.settings.resolved_llm_generate_model()
    repair_model = request.settings.resolved_llm_repair_model()
    reasoning = request.settings.resolved_llm_reasoning()
    log.info(
        "Using LLM repair model {} (provider={}; generate model={}; reasoning={})",
        repair_model,
        request.settings.resolved_llm_provider(),
        generate_model,
        reasoning.openrouter_payload() if reasoning.is_active() else None,
    )
    asset_entries = [entry.model_dump() for entry in request.asset_manifest.entries]
    repair_png = (
        request.figma_reference_png if generation_cfg.llm_repair_include_figma_png else None
    )

    def _error_fingerprint(errors: tuple[str, ...], detail: str) -> str:
        stable_errors = normalize_analyzer_errors_for_fingerprint(errors)
        return f"{detail}|{'|'.join(stable_errors[:8])}"

    last_fingerprint: str | None = None
    failed_attempts_history: list[str] = []
    cpi_supervisor_directive: str | None = None
    token_guard_escalation_bump = 0
    cpi_escalated = False
    screen_path = screen_file_path(
        request.resolved_feature,
        architecture=request.settings.agent.flutter.architecture,
    )
    prompt_escalator = RepairPromptEscalator(
        target_file=screen_path,
        max_attempts=max_attempts,
    )
    widgets_first = generation_cfg.llm_repair_widgets_first
    widget_analyze_kwargs = {
        "clean_tree": request.clean_tree,
        "widget_suffix": request.settings.agent.naming.widget_suffix,
        "uses_svg": any(
            item.asset_path.lower().endswith(".svg")
            for item in request.asset_manifest.entries
        ),
        "cluster_summary": request.cluster_summary,
        "cluster_min_count": generation_cfg.cluster_min_count,
        "destination_trees": request.destination_trees,
        "use_package_imports": generation_cfg.use_package_imports,
    }
    syntax_stall_limit = generation_cfg.llm_repair_syntax_stall_limit
    syntax_error_history: list[int] = []
    parse_level_failure: bool = False  # assigned per-attempt; pre-init guards first-iter use
    consecutive_noop_repairs = 0
    geometry_feedback = ""

    repair_baseline_planned = dict(result.planned_files)
    repair_baseline_generation: _GenerationSnapshot | None = None
    if result.llm_result.generation is not None:
        repair_baseline_generation = _snapshot_generation(result.llm_result.generation)

    last_good_planned = dict(repair_baseline_planned)
    last_good_generation = repair_baseline_generation

    for attempt in range(1, max_attempts + 1):
        analyze_outcome = analyze_planned_dart_files(
            result.planned_files,
            package_name=request.package_name,
            require_dart_sdk=require_dart_sdk,
            analyze_scope=analyze_scope,
            analyze_stage="llm_repair",
            analyze_attempt=attempt,
            flutter_sdk=request.settings.flutter_sdk or None,
            widgets_first=widgets_first,
            skip_planned_reconcile=True,
            skip_dart_format=True,
            **widget_analyze_kwargs,
        )
        if analyze_outcome.skipped:
            log.info("Analyze repair skipped: {}", analyze_outcome.detail)
            return result
        if analyze_outcome.passed:
            from dataclasses import replace

            from figma_flutter_agent.stages.runtime_geometry_check import (
                evaluate_runtime_geometry_for_repair,
            )

            geo_errors, geo_feedback = evaluate_runtime_geometry_for_repair(
                request,
                result.planned_files,
            )
            if geo_feedback:
                geometry_feedback = geo_feedback
            if geo_errors:
                log.warning(
                    "Runtime geometry gate failed ({} mismatch(es)); continuing repair loop",
                    len(geo_errors),
                )
                if geometry_feedback:
                    log.info("Geometry feedback for repair:\n{}", geometry_feedback)
                analyze_outcome = replace(
                    analyze_outcome,
                    passed=False,
                    errors=tuple(geo_errors),
                    detail="runtime_geometry_gate",
                )
            else:
                if attempt > 1:
                    log.info("Analyze repair succeeded after {} attempt(s)", attempt - 1)
                return result

        error_preview = "; ".join(analyze_outcome.errors[:3])
        if error_preview:
            log.warning(
                "Planned Dart analyze failed (attempt {}/{}): {} — {}",
                attempt,
                max_attempts,
                analyze_outcome.detail,
                error_preview,
            )
        else:
            log.warning(
                "Planned Dart analyze failed (attempt {}/{}): {}",
                attempt,
                max_attempts,
                analyze_outcome.detail,
            )
        syntax_error_history.append(_syntax_error_count(analyze_outcome))
        if (
            result.repair_attempts >= syntax_stall_limit
            and _syntax_repair_stalled(syntax_error_history, syntax_stall_limit)
            and parse_level_failure
        ):
            stall_msg = (
                f"LLM analyze repair stalled: syntax/format error count did not decrease "
                f"after {result.repair_attempts} repair round(s) "
                f"(counts={syntax_error_history[-syntax_stall_limit - 1 :]}). "
                f"Last errors: {'; '.join(analyze_outcome.errors[:3])}"
            )
            _rollback_repair_to_baseline(
                result,
                baseline_planned=repair_baseline_planned,
                baseline_generation=repair_baseline_generation,
                log=log,
                reason="syntax stall",
            )
            log.error(stall_msg)
            raise LlmRepairStalledError(stall_msg)

        fingerprint = _error_fingerprint(analyze_outcome.errors, analyze_outcome.detail)
        parse_level_failure = _is_syntax_level_analyze_failure(analyze_outcome)
        if parse_level_failure:
            format_paths = _format_failure_paths_from_outcome(analyze_outcome)
            if format_paths:
                pre_repair = dict(result.planned_files)
                result.planned_files = repair_planned_format_parse_failures(
                    result.planned_files,
                    format_paths,
                    analyze_errors=tuple(analyze_outcome.errors),
                )
                if result.planned_files != pre_repair:
                    log.info(
                        "Applied deterministic format-parse repair on {}",
                        ", ".join(format_paths),
                    )
                    quick_check = analyze_planned_dart_files(
                        result.planned_files,
                        package_name=request.package_name,
                        require_dart_sdk=require_dart_sdk,
                        analyze_scope=analyze_scope,
                        analyze_stage="llm_repair",
                        analyze_attempt=attempt,
                        flutter_sdk=request.settings.flutter_sdk or None,
                        widgets_first=widgets_first,
                        skip_planned_reconcile=True,
                        **widget_analyze_kwargs,
                    )
                    if quick_check.passed:
                        log.info(
                            "Format-parse repair fixed {} without LLM (attempt {})",
                            ", ".join(format_paths),
                            attempt,
                        )
                        return result
                log.warning(
                    "Syntax failure in {} — keeping broken planned files for in-place numbered repair",
                    ", ".join(format_paths),
                )
            syntax_directive = _critical_syntax_broken_directive(
                format_paths,
                rolled_back=False,
            )
            if generation_cfg.llm_repair_cpi_supervisor and not cpi_escalated:
                try:
                    set_llm_stage("repair_cpi_supervisor")
                    cpi_response = await llm_client.cpi_supervisor_async(
                        request.clean_tree,
                        feature_name=request.resolved_feature,
                        analyze_errors=[
                            syntax_directive,
                            *list(analyze_outcome.errors),
                        ],
                        failed_attempts_history=failed_attempts_history,
                    )
                    cpi_supervisor_directive = (
                        f"{syntax_directive}\n\n"
                        f"{cpi_response.pattern_interrupt_directive.strip()}"
                    )
                    cpi_escalated = True
                    log.warning(
                        "dart format parse failure; CPI supervisor engaged with "
                        "{} (attempt {}/{})",
                        "CRITICAL_SYNTAX_BROKEN_TAG",
                        attempt,
                        max_attempts,
                    )
                    preview = cpi_response.analysis.strip().replace("\n", " ")
                    if len(preview) > 160:
                        preview = f"{preview[:157]}..."
                    result.warnings.append(
                        f"CPI supervisor (CRITICAL_SYNTAX_BROKEN): {preview}"
                    )
                except LlmError as exc:
                    log.warning(
                        "CPI supervisor failed on dart format failure (attempt {}): {}",
                        attempt,
                        format_error_for_log(exc),
                    )
                    result.warnings.append(f"CPI supervisor failed: {exc}")
                    cpi_supervisor_directive = syntax_directive
            else:
                cpi_supervisor_directive = syntax_directive
        if fingerprint == last_fingerprint and not parse_level_failure:
            if _errors_suggest_extracted_widget_drift(analyze_outcome.errors):
                if _apply_extracted_widget_reference_fixup(request, result, log=log):
                    continue
            if generation_cfg.llm_repair_cpi_supervisor and not cpi_escalated:
                try:
                    set_llm_stage("repair_cpi_supervisor")
                    cpi_response = await llm_client.cpi_supervisor_async(
                        request.clean_tree,
                        feature_name=request.resolved_feature,
                        analyze_errors=list(analyze_outcome.errors),
                        failed_attempts_history=failed_attempts_history,
                    )
                    cpi_supervisor_directive = cpi_response.pattern_interrupt_directive.strip()
                    cpi_escalated = True
                    log.warning(
                        "Analyze repair stagnated; CPI supervisor issued pattern interrupt "
                        "(attempt {}/{})",
                        attempt,
                        max_attempts,
                    )
                    preview = cpi_response.analysis.strip().replace("\n", " ")
                    if len(preview) > 160:
                        preview = f"{preview[:157]}..."
                    result.warnings.append(f"CPI supervisor: {preview}")
                except LlmError as exc:
                    log.warning(
                        "CPI supervisor failed on stagnation (attempt {}): {}",
                        attempt,
                        format_error_for_log(exc),
                    )
                    result.warnings.append(f"CPI supervisor failed: {exc}")
            elif cpi_escalated:
                log.warning(
                    "Analyze repair: identical errors after CPI escalation on attempt {}/{}; "
                    "stopping",
                    attempt,
                    max_attempts,
                )
                result.warnings.append(
                    "Analyze repair stopped: recurring analyzer errors unchanged after "
                    "CPI pattern interrupt"
                )
                break
            elif _errors_suggest_extracted_widget_drift(analyze_outcome.errors):
                generation = result.llm_result.generation
                if generation is not None and generation.extracted_widgets:
                    log.warning(
                        "Analyze repair: identical extracted-widget errors on attempt {}/{}; "
                        "stopping early",
                        attempt,
                        max_attempts,
                    )
                    result.warnings.append(
                        "Analyze repair stopped: screenCode still references private "
                        "extracted widget names after deterministic reconcile"
                    )
                    break
            else:
                log.warning(
                    "Analyze repair: identical failure fingerprint on attempt {}/{}; "
                    "continuing until max attempts",
                    attempt,
                    max_attempts,
                )
        if not parse_level_failure:
            last_fingerprint = fingerprint
            pre_style_repair = dict(result.planned_files)
            result.planned_files = repair_planned_misplaced_text_style_params(
                result.planned_files,
                analyze_outcome.errors,
            )
            if result.planned_files != pre_style_repair:
                log.info("Applied deterministic Text(style) repair before LLM analyze repair")
                style_check = analyze_planned_dart_files(
                    result.planned_files,
                    package_name=request.package_name,
                    require_dart_sdk=require_dart_sdk,
                    analyze_scope=analyze_scope,
                    analyze_stage="llm_repair",
                    analyze_attempt=attempt,
                    flutter_sdk=request.settings.flutter_sdk or None,
                    widgets_first=widgets_first,
                    skip_planned_reconcile=True,
                    **widget_analyze_kwargs,
                )
                if style_check.passed:
                    log.info(
                        "Text(style) repair cleared analyzer errors without LLM (attempt {})",
                        attempt,
                    )
                    return result
                analyze_outcome = style_check

        if result.llm_result.generation is None:
            break

        if _errors_suggest_extracted_widget_drift(analyze_outcome.errors):
            if _apply_extracted_widget_reference_fixup(request, result, log=log):
                continue

        base_escalation_level = prompt_escalator.escalation_level(attempt)
        escalation_level = min(
            4,
            base_escalation_level + token_guard_escalation_bump,
        )
        repair_env: RepairEnvironmentContext | None = None
        repair_system_prompt: str | None = None
        repair_scope = build_repair_scope(
            feature_name=request.resolved_feature,
            planned_files=result.planned_files,
            current_generation=result.llm_result.generation,
            analyze_errors=list(analyze_outcome.errors),
            architecture=request.settings.agent.flutter.architecture,
            escalation_level=escalation_level,
            use_screen_ir=generation_cfg.use_screen_ir,
        )
        if generation_cfg.llm_repair_prompt_escalation:
            repair_env = build_repair_environment_context(
                scope=repair_scope,
                planned_files=result.planned_files,
                analyze_errors=list(analyze_outcome.errors),
                clean_tree=request.clean_tree,
                failed_attempts_history=failed_attempts_history,
                cpi_supervisor_directive=cpi_supervisor_directive,
            )
            repair_system_prompt = prompt_escalator.generate_system_prompt(
                attempt=attempt,
                env_context=repair_env,
                level=escalation_level,
            )

        from figma_flutter_agent.llm.repair_scope import (
            format_repair_attempt_record,
            repair_scope_planned_paths,
        )

        try:
            set_llm_stage("repair")
            repaired = await llm_client.repair_async(
                request.clean_tree,
                request.tokens,
                feature_name=request.resolved_feature,
                asset_manifest=asset_entries,
                current_generation=result.llm_result.generation,
                analyze_errors=list(analyze_outcome.errors),
                widget_hints=request.widget_hints,
                navigation_hints=request.navigation_hints,
                routing_enabled=request.routing_on,
                theme_variant=request.settings.agent.theme.variant,
                figma_reference_png=repair_png,
                planned_files=result.planned_files,
                architecture=request.settings.agent.flutter.architecture,
                failed_attempts_history=failed_attempts_history,
                cpi_supervisor_directive=cpi_supervisor_directive,
                repair_system_prompt=repair_system_prompt,
                escalation_level=escalation_level,
                geometry_feedback=geometry_feedback or None,
                use_screen_ir=generation_cfg.use_screen_ir,
                require_screen_ir=generation_cfg.require_screen_ir,
                project_dir=request.project_dir,
            )
        except LlmError as exc:
            log.warning(
                "LLM analyze repair attempt {} failed: {}",
                attempt,
                format_error_for_log(exc),
            )
            result.warnings.append(f"LLM analyze repair attempt {attempt} failed: {exc}")
            break

        if _repair_patch_has_duplicate_required_this(repaired):
            log.warning(
                "Token guard rejected LLM repair patch on attempt {}/{} "
                "(duplicate {required this.} within 100 chars)",
                attempt,
                max_attempts,
            )
            result.warnings.append(
                "Analyze repair patch rejected: duplicate constructor parameter blocks"
            )
            failed_attempts_history.append(
                format_repair_attempt_record(
                    attempt=attempt,
                    patch_codes=[("rejected", None, "duplicate required this.* in patch")],
                )
            )
            token_guard_escalation_bump = min(token_guard_escalation_bump + 1, 3)
            continue

        pre_repair_generation = (
            _snapshot_generation(result.llm_result.generation)
            if result.llm_result.generation is not None
            else None
        )
        if pre_repair_generation is not None and _repair_generation_unchanged(
            pre_repair_generation,
            repaired,
            use_screen_ir=generation_cfg.use_screen_ir,
        ):
            log.warning(
                "LLM analyze repair attempt {}/{}: no patch applied (unified diff rejected or empty)",
                attempt,
                max_attempts,
            )
            failed_attempts_history.append(
                format_repair_attempt_record(
                    attempt=attempt,
                    patch_codes=[
                        ("rejected", None, "unified diff did not apply to planned source"),
                    ],
                )
            )
            token_guard_escalation_bump = min(token_guard_escalation_bump + 1, 3)
            consecutive_noop_repairs += 1
            if (
                consecutive_noop_repairs >= syntax_stall_limit
                and parse_level_failure
            ):
                stall_msg = (
                    f"LLM analyze repair stalled: unified diff did not apply for "
                    f"{consecutive_noop_repairs} consecutive repair round(s) while "
                    f"dart format/analyze still fails. Last errors: "
                    f"{'; '.join(analyze_outcome.errors[:3])}"
                )
                _rollback_repair_to_baseline(
                    result,
                    baseline_planned=repair_baseline_planned,
                    baseline_generation=repair_baseline_generation,
                    log=log,
                    reason="noop diff stall",
                )
                log.error(stall_msg)
                raise LlmRepairStalledError(stall_msg)
            continue

        consecutive_noop_repairs = 0

        result.llm_result.generation = repaired
        result.repair_attempts = attempt
        result.planned_files = replan_planned_files(request, repaired)
        ast_scope_paths = repair_scope_planned_paths(repair_scope)
        gen_cfg = request.settings.agent.generation
        result.planned_files = reconcile_planned_dart_files(
            result.planned_files,
            blocked_asset_paths=request.blocked_asset_paths,
            typography_tokens=request.tokens,
            package_name=request.package_name,
            clean_tree=request.clean_tree,
            ast_full_reconcile_paths=ast_scope_paths or None,
            incremental=True,
            project_dir=request.project_dir,
            widget_suffix=request.settings.agent.naming.widget_suffix,
            uses_svg=any(
                item.asset_path.lower().endswith(".svg")
                for item in request.asset_manifest.entries
            ),
            use_package_imports=gen_cfg.use_package_imports,
            cluster_summary=request.cluster_summary,
            cluster_min_count=gen_cfg.cluster_min_count,
            destination_trees=request.destination_trees,
        )
        if _planned_files_have_delimiter_syntax_errors(result.planned_files):
            log.warning(
                "Repair attempt {} produced unparseable Dart; keeping broken files for next repair pass",
                attempt,
            )
            failed_attempts_history.append(
                format_repair_attempt_record(
                    attempt=attempt,
                    patch_codes=[("rejected", None, "syntax failure after repair patch")],
                )
            )
            continue

        last_good_planned = dict(result.planned_files)
        if result.llm_result.generation is not None:
            last_good_generation = _snapshot_generation(result.llm_result.generation)
        log.info("LLM analyze repair attempt {} complete; re-planned files", attempt)

        patch_codes: list[tuple[str, str | None, str]] = [
            ("screenCode", None, repaired.screen_code),
        ]
        patch_codes.extend(
            ("extractedWidget", widget.widget_name, widget.resolved_code())
            for widget in repaired.extracted_widgets
        )
        failed_attempts_history.append(
            format_repair_attempt_record(attempt=attempt, patch_codes=patch_codes)
        )

    if result.repair_attempts > 0:
        gen_cfg = request.settings.agent.generation
        result.planned_files = reconcile_planned_dart_files(
            result.planned_files,
            blocked_asset_paths=request.blocked_asset_paths,
            typography_tokens=request.tokens,
            package_name=request.package_name,
            clean_tree=request.clean_tree,
            incremental=True,
            project_dir=request.project_dir,
            widget_suffix=request.settings.agent.naming.widget_suffix,
            uses_svg=any(
                item.asset_path.lower().endswith(".svg")
                for item in request.asset_manifest.entries
            ),
            use_package_imports=gen_cfg.use_package_imports,
            cluster_summary=request.cluster_summary,
            cluster_min_count=gen_cfg.cluster_min_count,
            destination_trees=request.destination_trees,
        )
    final_outcome = analyze_planned_dart_files(
        result.planned_files,
        package_name=request.package_name,
        require_dart_sdk=require_dart_sdk,
        analyze_scope=analyze_scope,
        analyze_stage="llm_repair",
        analyze_attempt=max_attempts + 1,
        flutter_sdk=request.settings.flutter_sdk or None,
        widgets_first=widgets_first,
        skip_planned_reconcile=True,
        **widget_analyze_kwargs,
    )
    if not final_outcome.skipped and not final_outcome.passed:
        _rollback_repair_to_baseline(
            result,
            baseline_planned=repair_baseline_planned,
            baseline_generation=repair_baseline_generation,
            log=log,
            reason="attempt limit exhausted",
        )
        result.warnings.append(
            "LLM analyze repair exhausted "
            f"({result.repair_attempts}/{max_attempts} attempts); "
            "rolled back to pre-repair baseline."
        )
        remaining = "; ".join(final_outcome.errors[:3])
        log.warning(
            "Analyze repair exhausted after {} attempt(s); {} error(s) remain — {}",
            result.repair_attempts,
            len(final_outcome.errors),
            remaining or final_outcome.detail,
        )
    return result

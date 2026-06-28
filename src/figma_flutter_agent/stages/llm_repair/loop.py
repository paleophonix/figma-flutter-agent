"""Repair stage orchestration — analyze-repair loop and helpers."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.errors import (
    GenerationError,
    LlmError,
    LlmRepairStalledError,
    format_error_for_log,
)
from figma_flutter_agent.generator.dart.project_validation import (
    analyze_planned_dart_files,
    is_dart_analyze_timeout_detail,
    normalize_analyzer_errors_for_fingerprint,
)
from figma_flutter_agent.generator.paths import screen_file_path
from figma_flutter_agent.generator.planned.reconcile import (
    reconcile_planned_dart_files,
    repair_planned_format_parse_failures,
    repair_planned_misplaced_text_style_params,
)
from figma_flutter_agent.llm.repair_scope import (
    RepairEnvironmentContext,
    build_repair_environment_context,
    build_repair_scope,
)
from figma_flutter_agent.observability.llm_trace import set_llm_stage
from figma_flutter_agent.stages.llm_repair.cpi import (
    engage_cpi_supervisor_for_stagnation,
    engage_cpi_supervisor_for_syntax_failure,
)
from figma_flutter_agent.stages.llm_repair.finalize import (
    _rollback_repair_to_baseline,
    finalize_repair_loop,
)
from figma_flutter_agent.stages.llm_repair.models import (
    LlmRepairStageRequest,
    LlmRepairStageResult,
)
from figma_flutter_agent.stages.llm_repair.replan import replan_planned_files
from figma_flutter_agent.stages.llm_repair.snapshot import (
    _apply_extracted_widget_reference_fixup,
    _apply_widget_constructor_signature_reconcile,
    _errors_suggest_extracted_widget_drift,
    _errors_suggest_widget_constructor_signature_mismatch,
    _GenerationSnapshot,
    _repair_generation_unchanged,
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
from figma_flutter_agent.stages.repair_prompt_escalation import RepairPromptEscalator


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
            item.asset_path.lower().endswith(".svg") for item in request.asset_manifest.entries
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

    dict(repair_baseline_planned)

    analyze_timeout_retries = 0
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

        if analyze_outcome.toolchain_timeout or is_dart_analyze_timeout_detail(
            analyze_outcome.detail
        ):
            if analyze_timeout_retries < 1:
                analyze_timeout_retries += 1
                log.warning(
                    "Dart analyzer timeout (toolchain flake); retrying analyze before LLM repair"
                )
                continue
            stall_msg = (
                "Dart analyzer timed out repeatedly; refusing LLM repair for infrastructure "
                f"failure: {analyze_outcome.detail}"
            )
            log.error(stall_msg)
            raise GenerationError(stall_msg)

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
        if _errors_suggest_widget_constructor_signature_mismatch(analyze_outcome.errors):
            if _apply_widget_constructor_signature_reconcile(result):
                log.info(
                    "Applied deterministic widget constructor signature reconcile "
                    "(attempt {}/{})",
                    attempt,
                    max_attempts,
                )
                continue
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
                cpi_supervisor_directive = await engage_cpi_supervisor_for_syntax_failure(
                    llm_client,
                    request,
                    result,
                    syntax_directive=syntax_directive,
                    analyze_errors=analyze_outcome.errors,
                    failed_attempts_history=failed_attempts_history,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    log=log,
                )
                cpi_escalated = True
            else:
                cpi_supervisor_directive = syntax_directive
        if fingerprint == last_fingerprint and not parse_level_failure:
            if _errors_suggest_extracted_widget_drift(analyze_outcome.errors):
                if _apply_extracted_widget_reference_fixup(request, result, log=log):
                    continue
            if generation_cfg.llm_repair_cpi_supervisor and not cpi_escalated:
                directive = await engage_cpi_supervisor_for_stagnation(
                    llm_client,
                    request,
                    result,
                    analyze_errors=analyze_outcome.errors,
                    failed_attempts_history=failed_attempts_history,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    log=log,
                )
                if directive is not None:
                    cpi_supervisor_directive = directive
                cpi_escalated = True
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
            elif _errors_suggest_widget_constructor_signature_mismatch(
                analyze_outcome.errors
            ):
                log.warning(
                    "Analyze repair: widget constructor signature mismatch unchanged on "
                    "attempt {}/{}; stopping before further LLM repair",
                    attempt,
                    max_attempts,
                )
                result.warnings.append(
                    "Analyze repair stopped: widget constructor signature mismatch is "
                    "deterministic and not LLM-repairable"
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

        if _errors_suggest_widget_constructor_signature_mismatch(analyze_outcome.errors):
            log.warning(
                "Analyze repair: refusing LLM repair for widget constructor signature "
                "mismatch (attempt {}/{})",
                attempt,
                max_attempts,
            )
            result.warnings.append(
                "Analyze repair skipped LLM: widget constructor signature mismatch "
                "requires deterministic emitter/reconcile fix"
            )
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
            if consecutive_noop_repairs >= syntax_stall_limit and parse_level_failure:
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
                item.asset_path.lower().endswith(".svg") for item in request.asset_manifest.entries
            ),
            use_package_imports=gen_cfg.use_package_imports,
            cluster_summary=request.cluster_summary,
            cluster_min_count=gen_cfg.cluster_min_count,
            destination_trees=request.destination_trees,
            responsive_enabled=request.settings.agent.responsive.enabled,
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

    return finalize_repair_loop(
        result,
        request,
        repair_baseline_planned=repair_baseline_planned,
        repair_baseline_generation=repair_baseline_generation,
        require_dart_sdk=require_dart_sdk,
        analyze_scope=analyze_scope,
        widgets_first=widgets_first,
        max_attempts=max_attempts,
        widget_analyze_kwargs=widget_analyze_kwargs,
        log=log,
    )

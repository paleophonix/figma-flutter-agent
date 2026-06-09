"""LLM analyze repair loop for planned Dart files."""

from __future__ import annotations

import re
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
    PlannedAnalyzeOutcome,
    analyze_planned_dart_files,
    normalize_analyzer_errors_for_fingerprint,
    parse_format_failed_paths,
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
    WidgetIrNode,
)
from figma_flutter_agent.stages.llm import LlmStageResult
from figma_flutter_agent.stages.repair_prompt_escalation import RepairPromptEscalator

CRITICAL_SYNTAX_BROKEN_TAG = "CRITICAL_SYNTAX_BROKEN"

_EXTRACTED_WIDGET_DRIFT_MARKERS = (
    "isn't a class",
    "creation_with_non_type",
    "undefined_method",
)
_DUPLICATE_REQUIRED_THIS_RE = re.compile(r"\{required this\.")
_LIB_DART_PATH_RE = re.compile(r"(lib[/\\][^\s:]+\.dart)", re.IGNORECASE)


def _critical_syntax_broken_directive(
    format_paths: tuple[str, ...],
    *,
    rolled_back: bool,
) -> str:
    target = ", ".join(format_paths) if format_paths else "planned Dart sources"
    if rolled_back:
        return (
            f"{CRITICAL_SYNTAX_BROKEN_TAG}: Rolled back {target} to the last clean snapshot "
            "because the previous repair pass corrupted the file. The diff base is that clean "
            "version — fix the reported analyzer errors with minimal unified-diff hunks only; "
            "do not repeat broken patterns (duplicate `child:`, doubled constructor params)."
        )
    return (
        f"{CRITICAL_SYNTAX_BROKEN_TAG}: dart format could not parse {target}. "
        "The broken source is still on disk — apply minimal unified-diff hunks in place. "
        "Remove duplicate tokens (e.g. `child: child:`), fix constructors; do not rewrite whole files."
    )


def _format_failure_paths_from_outcome(outcome: PlannedAnalyzeOutcome) -> tuple[str, ...]:
    """Resolve ``formatFailedPaths`` from outcome metadata, format log, or error lines."""
    if outcome.format_failed_paths:
        return outcome.format_failed_paths
    paths = parse_format_failed_paths(outcome.analyze_output)
    if paths:
        return paths
    derived: list[str] = []
    for error in outcome.errors:
        match = _LIB_DART_PATH_RE.search(error.replace("\\", "/"))
        if match is not None:
            derived.append(match.group(1).replace("\\", "/"))
    return tuple(dict.fromkeys(derived))


def _repair_patch_has_duplicate_required_this(generation: FlutterGenerationResponse) -> bool:
    """Reject patches that repeat ``{required this.`` within a short window (token guard)."""
    sources = [
        generation.screen_code,
        *[widget.resolved_code() for widget in generation.extracted_widgets],
    ]
    for source in sources:
        if not source:
            continue
        for match in _DUPLICATE_REQUIRED_THIS_RE.finditer(source):
            start = max(0, match.start() - 50)
            window = source[start : match.start() + 100]
            if len(_DUPLICATE_REQUIRED_THIS_RE.findall(window)) >= 2:
                return True
    return False


def _rollback_planned_files_to_snapshot(
    planned: dict[str, str],
    snapshot: dict[str, str],
    paths: tuple[str, ...],
) -> dict[str, str]:
    updated = dict(planned)
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized in snapshot:
            updated[normalized] = snapshot[normalized]
    return updated


def rollback_file_on_syntax_error(
    planned: dict[str, str],
    snapshot: dict[str, str],
    *,
    paths: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Restore planned Dart sources from a pre-repair snapshot."""
    if paths is None:
        paths = tuple(sorted(path.replace("\\", "/") for path in planned if path.endswith(".dart")))
    return _rollback_planned_files_to_snapshot(planned, snapshot, paths)


def _planned_files_have_delimiter_syntax_errors(
    planned: dict[str, str],
    *,
    paths: tuple[str, ...] | None = None,
) -> bool:
    from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

    targets = paths or tuple(
        sorted(path.replace("\\", "/") for path in planned if path.endswith(".dart"))
    )
    for path in targets:
        if validate_dart_delimiters(planned.get(path, "")) is not None:
            return True
    return False


def _syntax_error_count(outcome: PlannedAnalyzeOutcome) -> int:
    """Approximate syntax/format failure severity for stall detection."""
    if _is_syntax_level_analyze_failure(outcome):
        paths = _format_failure_paths_from_outcome(outcome)
        if paths:
            return len(paths)
        return max(len(outcome.errors), 1)
    from figma_flutter_agent.llm.repair_scope import parse_analyze_error_locations

    locations = parse_analyze_error_locations(list(outcome.errors))
    if locations:
        return len(locations)
    markers = (
        "expected",
        "missing",
        "unterminated",
        "can't find",
        "could not format",
        "']'",
        "')'",
    )
    hits = sum(1 for error in outcome.errors if any(m in error.lower() for m in markers))
    return hits if hits else len(outcome.errors)


def _syntax_repair_stalled(history: list[int], stall_limit: int) -> bool:
    if len(history) < stall_limit + 1:
        return False
    window = history[-(stall_limit + 1) :]
    improvements = sum(
        1 for index in range(stall_limit) if window[index] > window[index + 1]
    )
    return improvements == 0


def _is_syntax_level_analyze_failure(
    outcome: PlannedAnalyzeOutcome,
) -> bool:
    detail = outcome.detail.lower()
    if "dart format failed" in detail:
        return True
    joined = " ".join(outcome.errors).lower()
    return "could not format" in joined or "could not be parsed" in joined


@dataclass(frozen=True)
class _GenerationSnapshot:
    screen_code: str
    screen_ir_fingerprint: str | None
    widget_codes: tuple[tuple[str, str], ...]
    widget_ir_fingerprints: tuple[tuple[str, str | None], ...]


def _widget_ir_fingerprint(widget_ir: WidgetIrNode | None) -> str | None:
    if widget_ir is None:
        return None
    return widget_ir.model_dump_json(by_alias=True)


def _screen_ir_fingerprint(screen_ir: ScreenIr | None) -> str | None:
    if screen_ir is None:
        return None
    return screen_ir.model_dump_json(by_alias=True)


def _snapshot_generation(
    generation: FlutterGenerationResponse,
) -> _GenerationSnapshot:
    return _GenerationSnapshot(
        screen_code=generation.screen_code,
        screen_ir_fingerprint=_screen_ir_fingerprint(generation.screen_ir),
        widget_codes=tuple(
            (widget.widget_name, widget.resolved_code())
            for widget in generation.extracted_widgets
        ),
        widget_ir_fingerprints=tuple(
            (widget.widget_name, _widget_ir_fingerprint(widget.widget_ir))
            for widget in generation.extracted_widgets
        ),
    )


def _restore_generation(
    generation: FlutterGenerationResponse,
    snapshot: _GenerationSnapshot,
) -> None:
    generation.screen_code = snapshot.screen_code
    if snapshot.screen_ir_fingerprint is not None:
        generation.screen_ir = ScreenIr.model_validate_json(snapshot.screen_ir_fingerprint)
    by_name = {name: code for name, code in snapshot.widget_codes}
    ir_by_name = dict(snapshot.widget_ir_fingerprints)
    for widget in generation.extracted_widgets:
        if widget.widget_name in by_name:
            widget.code = by_name[widget.widget_name]
        fingerprint = ir_by_name.get(widget.widget_name)
        if fingerprint is not None:
            widget.widget_ir = WidgetIrNode.model_validate_json(fingerprint)


def _repair_generation_unchanged(
    before: _GenerationSnapshot,
    after: FlutterGenerationResponse,
    *,
    use_screen_ir: bool,
) -> bool:
    after_snapshot = _snapshot_generation(after)
    if use_screen_ir and (
        before.screen_ir_fingerprint is not None
        or after_snapshot.screen_ir_fingerprint is not None
    ):
        return (
            before.screen_ir_fingerprint == after_snapshot.screen_ir_fingerprint
            and before.widget_ir_fingerprints == after_snapshot.widget_ir_fingerprints
        )
    return (
        before.screen_code == after_snapshot.screen_code
        and before.widget_codes == after_snapshot.widget_codes
    )


def _errors_suggest_extracted_widget_drift(errors: tuple[str, ...]) -> bool:
    joined = " ".join(errors).lower()
    return any(marker in joined for marker in _EXTRACTED_WIDGET_DRIFT_MARKERS) and "_" in joined


def _apply_extracted_widget_reference_fixup(
    request: LlmRepairStageRequest,
    result: LlmRepairStageResult,
    *,
    log: Any,
) -> bool:
    """Reconcile private widget usages in screenCode without another LLM call."""
    from figma_flutter_agent.generator.dart.llm_codegen import (
        reconcile_extracted_widget_references,
        reconcile_extracted_widget_references_in_planned,
    )

    generation = result.llm_result.generation
    if generation is None or not generation.extracted_widgets:
        return False
    pairs = [
        (widget.widget_name, widget.resolved_code())
        for widget in generation.extracted_widgets
        if widget.resolved_code()
    ]
    if generation.screen_code:
        reconciled = reconcile_extracted_widget_references(generation.screen_code, pairs)
        if reconciled == generation.screen_code:
            return False
        generation.screen_code = reconciled
        result.planned_files = replan_planned_files(
            request,
            generation,
            base_planned=result.planned_files,
        )
    else:
        updated = reconcile_extracted_widget_references_in_planned(
            result.planned_files,
            pairs,
        )
        if updated == result.planned_files:
            return False
        result.planned_files = updated
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
        uses_svg=any(item.kind == "icon" for item in request.asset_manifest.entries),
        use_package_imports=gen_cfg.use_package_imports,
        cluster_summary=request.cluster_summary,
        cluster_min_count=gen_cfg.cluster_min_count,
        destination_trees=request.destination_trees,
    )
    log.info("Reconciled extracted widget references in screenCode (deterministic)")
    return True


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
                        CRITICAL_SYNTAX_BROKEN_TAG,
                        attempt,
                        max_attempts,
                    )
                    preview = cpi_response.analysis.strip().replace("\n", " ")
                    if len(preview) > 160:
                        preview = f"{preview[:157]}..."
                    result.warnings.append(
                        f"CPI supervisor ({CRITICAL_SYNTAX_BROKEN_TAG}): {preview}"
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
                "(duplicate {{required this.}} within 100 chars)",
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

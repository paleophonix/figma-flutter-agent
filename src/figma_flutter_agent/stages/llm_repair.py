"""LLM analyze repair loop for planned Dart files."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import LlmError, format_error_for_log
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files
from figma_flutter_agent.generator.planner import GenerationPlanContext
from figma_flutter_agent.generator.validation import (
    analyze_planned_dart_files,
    normalize_analyzer_errors_for_fingerprint,
)
from figma_flutter_agent.llm.client import LlmClient
from figma_flutter_agent.observability.llm_trace import set_llm_stage
from figma_flutter_agent.parser.prototype import PrototypeNavigationPlan
from figma_flutter_agent.schemas import (
    AssetManifest,
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    FontManifest,
)
from figma_flutter_agent.stages.llm import LlmStageResult
from figma_flutter_agent.stages.plan import PlanStageRequest, plan_generation_output


@dataclass
class LlmRepairStageRequest:
    """Inputs for post-generation LLM repair and visual refine loops."""

    settings: Settings
    dry_run: bool
    project_dir: Path
    planned_files: dict[str, str]
    llm_result: LlmStageResult
    use_deterministic_screen: bool
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


def replan_planned_files(
    request: LlmRepairStageRequest,
    generation: FlutterGenerationResponse,
) -> dict[str, str]:
    """Re-plan generated Dart files from an updated LLM generation payload."""
    return plan_generation_output(
        PlanStageRequest(
            context=GenerationPlanContext(
                settings=request.settings,
                clean_tree=request.clean_tree,
                tokens=request.tokens,
                resolved_feature=request.resolved_feature,
                node_id=request.node_id,
                cluster_summary=request.cluster_summary,
                asset_manifest=request.asset_manifest,
                font_manifest=request.font_manifest,
                generation=generation,
                destination_generations=request.llm_result.destination_generations,
                destination_trees=request.destination_trees,
                navigation_plan=request.navigation_plan,
                figma_root=request.figma_root,
                routing_on=request.routing_on,
                package_name=request.package_name,
                blocked_asset_paths=request.blocked_asset_paths,
            ),
        ),
    ).planned_files


def _should_run_repair(request: LlmRepairStageRequest) -> bool:
    generation_cfg = request.settings.agent.generation
    if request.dry_run:
        return False
    if request.use_deterministic_screen:
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
        LlmError: Not raised; repair failures are logged and the last planned state is kept.
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
    log.info(
        "Using LLM repair model {} (provider={}; generate model={}; reasoning disabled for repair)",
        repair_model,
        request.settings.resolved_llm_provider(),
        generate_model,
    )
    asset_entries = [entry.model_dump() for entry in request.asset_manifest.entries]
    repair_png = (
        request.figma_reference_png if generation_cfg.llm_repair_include_figma_png else None
    )

    def _error_fingerprint(errors: tuple[str, ...], detail: str) -> str:
        stable_errors = normalize_analyzer_errors_for_fingerprint(errors)
        return f"{detail}|{'|'.join(stable_errors[:8])}"

    last_fingerprint: str | None = None

    for attempt in range(1, max_attempts + 1):
        result.planned_files = reconcile_planned_dart_files(
            result.planned_files,
            blocked_asset_paths=request.blocked_asset_paths,
        )
        analyze_outcome = analyze_planned_dart_files(
            result.planned_files,
            package_name=request.package_name,
            require_dart_sdk=require_dart_sdk,
            analyze_scope=analyze_scope,
            analyze_stage="llm_repair",
            analyze_attempt=attempt,
            flutter_sdk=request.settings.flutter_sdk or None,
        )
        if analyze_outcome.skipped:
            log.info("Analyze repair skipped: {}", analyze_outcome.detail)
            return result
        if analyze_outcome.passed:
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
        fingerprint = _error_fingerprint(analyze_outcome.errors, analyze_outcome.detail)
        parse_level_failure = "dart format failed" in analyze_outcome.detail.lower()
        if fingerprint == last_fingerprint and not parse_level_failure:
            log.warning(
                "Analyze repair: identical failure fingerprint on attempt {}/{}; "
                "continuing until max attempts",
                attempt,
                max_attempts,
            )
        if not parse_level_failure:
            last_fingerprint = fingerprint

        if result.llm_result.generation is None:
            break

        try:
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
            )
        except LlmError as exc:
            log.warning(
                "LLM analyze repair attempt {} failed: {}",
                attempt,
                format_error_for_log(exc),
            )
            result.warnings.append(f"LLM analyze repair attempt {attempt} failed: {exc}")
            break

        result.llm_result.generation = repaired
        result.repair_attempts = attempt
        result.planned_files = replan_planned_files(request, repaired)
        log.info("LLM analyze repair attempt {} complete; re-planned files", attempt)

    final_outcome = analyze_planned_dart_files(
        result.planned_files,
        package_name=request.package_name,
        require_dart_sdk=require_dart_sdk,
        analyze_scope=analyze_scope,
        analyze_stage="llm_repair",
        analyze_attempt=max_attempts + 1,
        flutter_sdk=request.settings.flutter_sdk or None,
    )
    if not final_outcome.skipped and not final_outcome.passed:
        result.warnings.append(
            "LLM analyze repair exhausted "
            f"({result.repair_attempts}/{max_attempts} attempts); "
            "write may fail dart analyze."
        )
        remaining = "; ".join(final_outcome.errors[:3])
        log.warning(
            "Analyze repair exhausted after {} attempt(s); {} error(s) remain — {}",
            result.repair_attempts,
            len(final_outcome.errors),
            remaining or final_outcome.detail,
        )
    return result

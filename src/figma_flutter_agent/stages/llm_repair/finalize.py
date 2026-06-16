"""Repair-loop finalization: rollback helper and post-loop reconcile/analyze."""

from __future__ import annotations

from loguru import logger

from figma_flutter_agent.generator.dart.project_validation import analyze_planned_dart_files
from figma_flutter_agent.generator.planned.reconcile import reconcile_planned_dart_files
from figma_flutter_agent.stages.llm_repair.models import LlmRepairStageResult
from figma_flutter_agent.stages.llm_repair.snapshot import _GenerationSnapshot, _restore_generation


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


def finalize_repair_loop(
    result: LlmRepairStageResult,
    request,
    *,
    repair_baseline_planned: dict[str, str],
    repair_baseline_generation: _GenerationSnapshot | None,
    require_dart_sdk: bool,
    analyze_scope,
    widgets_first: bool,
    max_attempts: int,
    widget_analyze_kwargs: dict,
    log=None,
) -> LlmRepairStageResult:
    """Reconcile final planned files, run a closing analyze, and roll back if still failing.

    Args:
        result: Current repair-stage result, mutated in place.
        request: Original repair-stage request (for project context).
        repair_baseline_planned: Planned files snapshot before the repair loop started.
        repair_baseline_generation: Generation snapshot before the repair loop started.
        require_dart_sdk: Whether the analyzer requires the Dart SDK to be present.
        analyze_scope: Scope passed to `analyze_planned_dart_files`.
        widgets_first: Whether widgets are analyzed before the screen.
        max_attempts: Maximum repair attempts configured for the loop.
        widget_analyze_kwargs: Shared kwargs forwarded to `analyze_planned_dart_files`.
        log: Bound logger; defaults to the module logger if not provided.

    Returns:
        The mutated `result`, with planned files reconciled and rolled back on failure.
    """
    log = log or logger
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
                item.asset_path.lower().endswith(".svg") for item in request.asset_manifest.entries
            ),
            use_package_imports=gen_cfg.use_package_imports,
            cluster_summary=request.cluster_summary,
            cluster_min_count=gen_cfg.cluster_min_count,
            destination_trees=request.destination_trees,
            responsive_enabled=request.settings.agent.responsive.enabled,
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

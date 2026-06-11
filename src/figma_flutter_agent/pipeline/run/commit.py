"""Pre-write analysis, write, snapshot, and result-finalization phases."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from figma_flutter_agent.config import Settings
    from figma_flutter_agent.pipeline.incremental import DesignHashes, IncrementalContext
    from figma_flutter_agent.pipeline.llm import LlmOutcome
    from figma_flutter_agent.pipeline.result import PipelineResult
    from figma_flutter_agent.pipeline_context import PipelineContext
    from figma_flutter_agent.schemas import FigmaParsedUrl


def run_write_phase(
    ctx: PipelineContext,
    *,
    parsed: FigmaParsedUrl,
    settings: Settings,
    incremental: IncrementalContext,
    hashes: DesignHashes,
    llm_outcome: LlmOutcome,
    planned_files: dict[str, str],
    package_name: str,
    pipeline_deps: Any,
    log: Any,
    force_llm_regen: bool,
    regenerate_templates: bool,
    resolved_sync: bool,
    result: PipelineResult,
) -> None:
    """Execute pre-write validation, file write, and snapshot persistence.

    Mutates ``result.written_files`` in place.

    Args:
        ctx: Mutable pipeline context.
        parsed: Parsed Figma URL components.
        settings: Pipeline settings.
        incremental: Incremental sync context.
        hashes: Design content hashes.
        llm_outcome: Outcome from the LLM + plan stages.
        planned_files: Planned Dart file contents keyed by relative path.
        package_name: Flutter package name.
        pipeline_deps: Injectable pipeline dependencies.
        log: Bound logger instance.
        force_llm_regen: Whether LLM regen was forced.
        regenerate_templates: Whether to force template regeneration.
        resolved_sync: Effective sync-enabled flag.
        result: PipelineResult to mutate with written files.
    """
    from figma_flutter_agent.observability import log_stage
    from figma_flutter_agent.pipeline.helpers import (
        enforce_emit_parse_gate,
        persist_planned_dart_debug_snapshot,
    )
    from figma_flutter_agent.pipeline.incremental import (
        maybe_persist_snapshot,
        select_planned_writes,
    )
    from figma_flutter_agent.pipeline.llm import ensure_llm_output_or_raise
    from figma_flutter_agent.stages import WriteStageRequest

    clean_tree = ctx.clean_tree
    tokens = ctx.tokens
    assert clean_tree is not None and tokens is not None
    architecture = settings.agent.flutter.architecture

    def _persist_dart_debug_bug(files: dict[str, str]) -> None:
        persist_planned_dart_debug_snapshot(
            ctx.project_dir,
            feature_name=ctx.resolved_feature,
            planned_files=files,
            package_name=package_name,
            architecture=architecture,
            snapshot="bug",
        )

    ensure_llm_output_or_raise(
        llm_result=llm_outcome.llm_result,
        tree_changed=incremental.tree_changed,
        force_llm_regen=force_llm_regen,
    )

    files_to_write = select_planned_writes(
        resolved_sync=resolved_sync,
        previous_snapshot=incremental.previous_snapshot,
        file_key=parsed.file_key,
        node_id=parsed.node_id,
        hashes=hashes,
        planned_files=planned_files,
        regenerate_templates=regenerate_templates,
        settings=settings,
        clean_tree=clean_tree,
        cluster_summary=ctx.cluster_summary,
        feature_name=ctx.resolved_feature,
        force_screen_regen=force_llm_regen
        or (
            llm_outcome.llm_result.generation is not None
            and not llm_outcome.llm_result.skipped_incremental
        ),
    )

    if files_to_write:
        write_subset = {path: planned_files[path] for path in files_to_write}
        enforce_emit_parse_gate(
            settings,
            write_subset,
            package_name=package_name,
            stage="pre_write_parse_gate",
            typography_tokens=tokens,
            clean_tree=clean_tree,
            feature_name=ctx.resolved_feature,
            routing_on=any(
                path.replace("\\", "/").startswith("lib/core/app_router")
                for path in planned_files
            ),
            on_parse_gate_failure=_persist_dart_debug_bug,
        )
    if files_to_write:
        from figma_flutter_agent.generator.planned.reconcile import (
            force_polluted_feature_screens_to_layout,
        )

        planned_files = force_polluted_feature_screens_to_layout(
            planned_files,
            package_name=package_name,
            responsive_enabled=settings.agent.responsive.enabled,
            project_dir=ctx.project_dir,
        )

    if files_to_write and settings.agent.validation.spec23_dart_analyze:
        from figma_flutter_agent.errors import GenerationError
        from figma_flutter_agent.generator.dart.project_validation import analyze_planned_dart_files

        gen_cfg = settings.agent.generation
        pre_write_analyze = analyze_planned_dart_files(
            {path: planned_files[path] for path in files_to_write},
            package_name=package_name,
            require_dart_sdk=settings.agent.validation.require_dart_sdk,
            analyze_scope=settings.agent.validation.analyze_scope,
            analyze_stage="pre_write",
            flutter_sdk=settings.flutter_sdk or None,
            typography_tokens=tokens,
            clean_tree=clean_tree,
            skip_planned_reconcile=True,
            widget_suffix=settings.agent.naming.widget_suffix,
            uses_svg=any(
                item.asset_path.lower().endswith(".svg")
                for item in ctx.asset_manifest.entries
            ),
            cluster_summary=ctx.cluster_summary,
            cluster_min_count=gen_cfg.cluster_min_count,
            destination_trees=ctx.destination_trees,
            use_package_imports=gen_cfg.use_package_imports,
        )
        if not pre_write_analyze.skipped and not pre_write_analyze.passed:
            _persist_dart_debug_bug(
                {path: planned_files[path] for path in files_to_write},
            )
            preview = "; ".join(pre_write_analyze.errors[:5])
            raise GenerationError(
                "Refusing to write generated Dart: planned files fail analyze "
                f"({pre_write_analyze.detail}): {preview}"
            )

    routing_type = settings.agent.routing.type
    if files_to_write:
        from figma_flutter_agent.generator.planned.reconcile.bootstrap_refresh import (
            build_planned_bootstrap_context,
        )

        bootstrap_context = build_planned_bootstrap_context(
            settings=settings,
            package_name=package_name,
            feature_name=ctx.resolved_feature,
            app_title=clean_tree.name if clean_tree is not None else None,
            routing_on=any(
                path.replace("\\", "/").startswith("lib/core/app_router")
                for path in planned_files
            ),
        )
        with log_stage(log, "write"):
            write_result = pipeline_deps.commit_planned_files(
                WriteStageRequest(
                    project_dir=ctx.project_dir,
                    files_to_write=files_to_write,
                    package_name=package_name,
                    emit_parse_gate=settings.agent.validation.emit_parse_gate,
                    asset_manifest=ctx.asset_manifest,
                    font_manifest=ctx.font_manifest,
                    routing_type=routing_type,
                    state_management_type=settings.agent.state_management.type,
                    enable_backup=settings.enable_safety_backup,
                    require_dart_sdk=settings.agent.validation.require_dart_sdk,
                    flutter_sdk=settings.flutter_sdk or None,
                    strict_preservation=settings.agent.validation.strict_preservation,
                    analyze_scope=settings.agent.validation.analyze_scope,
                    analyze_relative_paths=sorted(files_to_write),
                    planned_files_for_widget_cleanup=planned_files,
                    dart_writer_factory=pipeline_deps.dart_writer_factory,
                    feature_name=ctx.resolved_feature,
                    architecture=architecture,
                    bootstrap_context=bootstrap_context,
                    on_parse_gate_failure=_persist_dart_debug_bug,
                ),
            )
        result.written_files = write_result.written_files
    else:
        log.info("Incremental sync: no files required updates")

    maybe_persist_snapshot(
        log,
        project_dir=ctx.project_dir,
        resolved_sync=resolved_sync,
        file_key=parsed.file_key,
        node_id=parsed.node_id,
        feature_name=ctx.resolved_feature,
        hashes=hashes,
        planned_files=planned_files,
        files_to_write=files_to_write,
        previous_snapshot=incremental.previous_snapshot,
        reference_image_hash=ctx.reference_image_hash,
        clean_tree=clean_tree,
    )

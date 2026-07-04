"""Core end-to-end generation pipeline logic."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from figma_flutter_agent.assets.webp import webp_conversion_available
from figma_flutter_agent.config import Settings
from figma_flutter_agent.dart_error_log import (
    bind_dart_error_session,
)
from figma_flutter_agent.errors import FlutterProjectError, PipelineError
from figma_flutter_agent.figma.url import build_figma_url, parse_figma_url
from figma_flutter_agent.generator.pubspec import read_pubspec_name
from figma_flutter_agent.observability import log_stage, new_run_id
from figma_flutter_agent.observability.llm_trace import bind_pipeline_observability
from figma_flutter_agent.observability.loki_sink import LOKI_APP_MAIN, LOKI_TEAM_DEFAULT
from figma_flutter_agent.pipeline.deps import (
    PipelineDependencies,
    default_pipeline_dependencies,
)
from figma_flutter_agent.pipeline.dump import (
    _resolve_existing_raw_dump_path,
    resolve_frame_metadata_from_dump,
)
from figma_flutter_agent.pipeline.dump_prefetch import ScreenDumpPrefetch
from figma_flutter_agent.pipeline.helpers import (
    resolve_early_feature_slug,
    resolve_manifest_cached_dump,
    routing_enabled,
    validate_project_dir,
    validate_runtime_credentials,
)
from figma_flutter_agent.pipeline.incremental import (
    design_hashes,
    load_incremental_context,
)
from figma_flutter_agent.pipeline.llm import execute_llm_stage
from figma_flutter_agent.pipeline.result import PipelineResult
from figma_flutter_agent.pipeline_context import PipelineContext
from figma_flutter_agent.render_log import (
    bind_render_log_session,
    bound_render_log_dir,
    clear_render_log_session,
    render_log_enabled_for_pipeline,
)
from figma_flutter_agent.stages import (
    export_figma_assets,
    fetch_figma_frame,
    parse_figma_frame,
    run_analyze_repair_loop,
)

from .commit import run_write_phase
from .fetch import load_dev_mode_css
from .stages import (
    apply_viewport_inset_and_resolve_feature,
    prepare_navigation_and_subtree,
    resolve_offline_reference_png,
    run_dump_fetch_parse_phase,
    run_live_fetch_parse_phase,
    run_llm_and_plan_phase,
    run_validate_repair_refine_phase,
)


async def run_pipeline(
    settings: Settings,
    *,
    figma_url: str | None = None,
    project_dir: Path,
    feature_name: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    sync_enabled: bool | None = None,
    regenerate_templates: bool = False,
    force_llm_regen: bool = False,
    from_dump: Path | None = None,
    from_ir: bool = False,
    from_ir_path: Path | None = None,
    require_figma_token: bool | None = None,
    force_live_fetch: bool = False,
    deps: PipelineDependencies | None = None,
    pipeline_invocation: str = "default",
    llm_compare: bool = False,
    dump_prefetch: ScreenDumpPrefetch | None = None,
) -> PipelineResult:
    """Execute the Figma to Flutter generation pipeline."""
    if verbose:
        logger.warning(
            "Verbose mode enabled: raw/processed design data will be dumped under "
            ".debug/<feature>/raw.json and .debug/<feature>/processed.json. "
            "Ensure this directory is excluded from version control if it contains proprietary data."
        )

    validate_project_dir(project_dir)
    from figma_flutter_agent.debug.agent_logs import purge_legacy_agent_debug_log_dirs
    from figma_flutter_agent.debug.migrate import ensure_project_debug_layout
    from figma_flutter_agent.debug.session_reset import reset_pipeline_run_debug_dirs
    from figma_flutter_agent.debug.terminal_log import bind_terminal_log_session

    ensure_project_debug_layout(project_dir)
    purge_legacy_agent_debug_log_dirs()
    pipeline_deps = deps or default_pipeline_dependencies()

    if figma_url is None:
        if from_dump is None:
            raise FlutterProjectError(
                "figma_url is required unless --from-dump points to a cached raw layout dump"
            )
        dump_meta = resolve_frame_metadata_from_dump(
            project_dir,
            from_dump,
            feature_name=feature_name,
        )
        figma_url = build_figma_url(dump_meta.file_key, dump_meta.node_id)
        if feature_name is None and dump_meta.feature_name is not None:
            feature_name = dump_meta.feature_name
        logger.info(
            "Resolved offline frame metadata from dump: file_key={} node_id={}",
            dump_meta.file_key,
            dump_meta.node_id,
        )

    if from_dump is not None:
        from_dump = _resolve_existing_raw_dump_path(
            project_dir,
            from_dump,
            feature_name=feature_name,
        )

    parsed = parse_figma_url(figma_url)
    if from_dump is None and not force_live_fetch:
        auto_dump = resolve_manifest_cached_dump(
            project_dir,
            feature_name=feature_name,
            node_id=parsed.node_id,
            file_key=parsed.file_key,
        )
        if auto_dump is not None:
            from_dump = auto_dump
            logger.info(
                "Using cached manifest dump (skip live Figma fetch): {}",
                from_dump.as_posix(),
            )

    offline_dump_mode = from_dump is not None and not force_live_fetch

    use_cached_ir = from_ir or from_ir_path is not None
    needs_figma_token = (
        require_figma_token if require_figma_token is not None else from_dump is None
    )
    validate_runtime_credentials(
        settings,
        dry_run=dry_run,
        require_figma_token=needs_figma_token,
        require_llm_api_key=not use_cached_ir,
    )
    run_id = new_run_id()
    bind_pipeline_observability(run_id=run_id, settings=settings)
    bind_dart_error_session(run_id=run_id, project_dir=project_dir, feature_name=feature_name)
    clear_render_log_session()
    if render_log_enabled_for_pipeline(settings, dry_run=dry_run):
        bind_render_log_session(
            run_id=run_id,
            project_dir=project_dir,
            feature_name=feature_name,
        )
    resolved_sync = settings.agent.sync.enabled if sync_enabled is None else sync_enabled
    ctx = PipelineContext(
        settings=settings,
        project_dir=project_dir,
        parsed=parsed,
        dry_run=dry_run,
        verbose=verbose,
        resolved_sync=resolved_sync,
        feature_name=feature_name,
        regenerate_templates=regenerate_templates,
    )
    ctx.pipeline_run_id = run_id
    log = logger.bind(
        run_id=run_id,
        file_key=parsed.file_key,
        node_id=parsed.node_id,
        project_dir=str(project_dir),
        dry_run=dry_run,
        sync_enabled=resolved_sync,
        app=LOKI_APP_MAIN,
        team=LOKI_TEAM_DEFAULT,
    )
    log.info("Generation mode: llm-ir")
    log.info("Pipeline run started")
    if settings.agent.runtime.cleanup_stale_processes_on_start:
        from figma_flutter_agent.tools.stale_process_cleanup import cleanup_stale_agent_processes

        cleanup_stale_agent_processes()

    # ------------------------------------------------------------------
    # Dev Mode CSS dump (Phase 3) — load once, pass to every parse call.
    # ------------------------------------------------------------------
    dev_mode_dump, dev_mode_css_override = await load_dev_mode_css(settings, log)

    if settings.agent.assets.webp and not webp_conversion_available():
        ctx.warnings.append(
            "WebP export is enabled (assets.webp) but Pillow is not installed; keeping PNG assets. "
            "Install with: poetry install (Pillow is a default dependency)."
        )

    early_feature = resolve_early_feature_slug(
        settings,
        feature_name=feature_name,
        from_dump=from_dump,
        project_dir=project_dir,
    )
    active_run_meta_feature: str | None = None
    if early_feature and not dry_run:
        from figma_flutter_agent.debug.run_meta import begin_run_meta

        begin_run_meta(project_dir, early_feature, pipeline_run_id=run_id)
        active_run_meta_feature = early_feature

    async def _complete_run() -> PipelineResult:
        nonlocal active_run_meta_feature
        run_log = log

        if from_dump is not None:
            await run_dump_fetch_parse_phase(
                ctx,
                log=run_log,
                parsed=parsed,
                settings=settings,
                project_dir=project_dir,
                from_dump=from_dump,
                dry_run=dry_run,
                offline_dump_mode=offline_dump_mode,
                pipeline_deps=pipeline_deps,
                dev_mode_dump=dev_mode_dump,
                dev_mode_css_override=dev_mode_css_override,
                parse_fn=parse_figma_frame,
                dump_prefetch=dump_prefetch,
            )
        else:
            await run_live_fetch_parse_phase(
                ctx,
                log=run_log,
                parsed=parsed,
                settings=settings,
                project_dir=project_dir,
                dry_run=dry_run,
                verbose=verbose,
                pipeline_deps=pipeline_deps,
                dev_mode_dump=dev_mode_dump,
                dev_mode_css_override=dev_mode_css_override,
                parse_fn=parse_figma_frame,
                fetch_fn=fetch_figma_frame,
                export_assets_fn=export_figma_assets,
            )

        ctx.require_parse_complete()
        with log_stage(run_log, "analyze"):
            ctx.collect_analysis_warnings()

        clean_tree = ctx.clean_tree
        tokens = ctx.tokens
        dedup_result = ctx.dedup_result
        assert clean_tree is not None and tokens is not None and dedup_result is not None

        run_log = apply_viewport_inset_and_resolve_feature(
            ctx,
            log=run_log,
            settings=settings,
            project_dir=project_dir,
            feature_name=feature_name,
            from_dump=from_dump,
            dry_run=dry_run,
            verbose=verbose,
        )
        resolved_feature = ctx.resolved_feature
        if not dry_run and resolved_feature:
            from figma_flutter_agent.debug.run_meta import (
                reconcile_run_meta_feature_identity,
                update_run_meta_stage,
            )

            active_run_meta_feature = reconcile_run_meta_feature_identity(
                project_dir,
                pipeline_run_id=run_id,
                early_feature=active_run_meta_feature,
                resolved_feature=resolved_feature,
            )
            parse_hashes = design_hashes(clean_tree, tokens)
            update_run_meta_stage(
                project_dir,
                active_run_meta_feature,
                pipeline_run_id=run_id,
                status="parsed",
                clean_tree_hash=parse_hashes.tree_hash,
            )
        reset_pipeline_run_debug_dirs(project_dir, resolved_feature)
        bind_terminal_log_session(project_dir, resolved_feature)
        bind_dart_error_session(
            run_id=run_id,
            project_dir=project_dir,
            feature_name=resolved_feature,
        )

        hashes = design_hashes(clean_tree, tokens)
        incremental, sync_warnings = load_incremental_context(
            project_dir,
            settings,
            resolved_sync=resolved_sync,
            hashes=hashes,
            feature_name=resolved_feature,
        )
        ctx.warnings.extend(sync_warnings)
    
        routing_type = settings.agent.routing.type
        routing_on = routing_enabled(settings)
        navigation_plan, route_transitions, navigation_hints, widget_hints = (
            prepare_navigation_and_subtree(
                ctx,
                settings=settings,
                parsed=parsed,
                routing_on=routing_on,
            )
        )
        ctx.persist_optional_reports(
            feature_slug=ctx.resolved_feature,
            route_transitions=route_transitions or None,
            routing_type=routing_type,
        )
    
        from figma_flutter_agent.pipeline.run.stages import run_reusable_candidates_phase
    
        widget_hints = await run_reusable_candidates_phase(
            ctx,
            settings=settings,
            project_dir=project_dir,
            widget_hints=widget_hints,
            tokens=tokens,
            pipeline_deps=pipeline_deps,
        )
    
        attach_to_llm = settings.agent.generation.llm_figma_reference_image
        needs_reference_png = (
            attach_to_llm
            or settings.agent.validation.export_figma_reference
            or settings.agent.generation.llm_visual_refine
            or settings.agent.dev.debug_capture
        )
        if (
            not dry_run
            and from_dump is not None
            and needs_reference_png
            and ctx.reference_image_png is None
        ):
            await resolve_offline_reference_png(
                ctx,
                log=run_log,
                parsed=parsed,
                settings=settings,
                project_dir=project_dir,
                offline_dump_mode=offline_dump_mode,
                pipeline_deps=pipeline_deps,
            )
    
        if llm_compare:
            from figma_flutter_agent.llm.compare import run_llm_ir_compare
    
            if ctx.asset_manifest is None:
                raise PipelineError("LLM compare requires a parsed asset manifest")
            with log_stage(run_log, "llm_compare"):
                compare_result = await run_llm_ir_compare(
                    settings=settings,
                    project_dir=project_dir,
                    resolved_feature=resolved_feature,
                    clean_tree=clean_tree,
                    tokens=tokens,
                    asset_manifest=ctx.asset_manifest,
                    widget_hints=widget_hints,
                    navigation_hints=navigation_hints,
                    routing_on=routing_on,
                    figma_reference_png=ctx.reference_image_png,
                    pipeline_deps=pipeline_deps,
                )
            ctx.warnings.extend(compare_result.warnings)
            if not dry_run and ctx.resolved_feature:
                from figma_flutter_agent.compiler.generation_config_fingerprint import (
                    generation_config_fingerprint,
                )
                from figma_flutter_agent.debug.run_meta import write_run_meta

                _, cfg_hash = generation_config_fingerprint(settings)
                write_run_meta(
                    project_dir,
                    ctx.resolved_feature,
                    pipeline_run_id=run_id,
                    writeback="skipped",
                    written_files=[],
                    clean_tree_hash=hashes.tree_hash,
                    generation_config_hash=cfg_hash,
                )
            return PipelineResult(
                clean_tree=clean_tree,
                tokens=tokens,
                planned_files=[],
                warnings=ctx.warnings,
                run_id=run_id,
            )
    
        llm_outcome, planned_files = await run_llm_and_plan_phase(
            ctx,
            log=run_log,
            settings=settings,
            parsed=parsed,
            project_dir=project_dir,
            dry_run=dry_run,
            resolved_sync=resolved_sync,
            incremental=incremental,
            clean_tree=clean_tree,
            tokens=tokens,
            navigation_plan=navigation_plan,
            navigation_hints=navigation_hints,
            widget_hints=widget_hints,
            routing_on=routing_on,
            use_cached_ir=use_cached_ir,
            from_ir_path=from_ir_path,
            force_llm_regen=force_llm_regen,
            pipeline_deps=pipeline_deps,
            execute_llm_stage_fn=execute_llm_stage,
        )
        package_name = read_pubspec_name(project_dir)
        architecture = settings.agent.flutter.architecture
    
        planned_files, _post_gen_request = await run_validate_repair_refine_phase(
            ctx,
            log=run_log,
            settings=settings,
            parsed=parsed,
            project_dir=project_dir,
            dry_run=dry_run,
            clean_tree=clean_tree,
            tokens=tokens,
            incremental=incremental,
            navigation_plan=navigation_plan,
            navigation_hints=navigation_hints,
            widget_hints=widget_hints,
            routing_on=routing_on,
            use_cached_ir=use_cached_ir,
            llm_outcome=llm_outcome,
            planned_files=planned_files,
            package_name=package_name,
            architecture=architecture,
            pipeline_deps=pipeline_deps,
            run_analyze_repair_loop_fn=run_analyze_repair_loop,
        )
    
        result = PipelineResult(
            clean_tree=clean_tree,
            tokens=tokens,
            planned_files=sorted(planned_files.keys()),
            warnings=ctx.warnings,
            run_id=run_id,
            clean_tree_hash=hashes.tree_hash,
            colors_hash=hashes.colors_hash,
            typography_hash=hashes.typography_hash,
            spacing_hash=hashes.spacing_hash,
        )
    
        if dry_run:
            return result
    
        if ctx.analyze_repair_exhausted:
            from figma_flutter_agent.errors import GenerationError
    
            preview = (
                "; ".join(
                    warning for warning in ctx.warnings if "analyze repair exhausted" in warning.lower()
                )
                or "planned Dart analyze failed after repair loop"
            )
            raise GenerationError(
                f"Skipping write: planned Dart still fails analyze after repair exhaustion ({preview})"
            )
    
        run_write_phase(
            ctx,
            parsed=parsed,
            settings=settings,
            incremental=incremental,
            hashes=hashes,
            llm_outcome=llm_outcome,
            planned_files=planned_files,
            package_name=package_name,
            pipeline_deps=pipeline_deps,
            log=run_log,
            force_llm_regen=force_llm_regen,
            regenerate_templates=regenerate_templates,
            resolved_sync=resolved_sync,
            result=result,
        )
    
        from figma_flutter_agent.dart_error_log import bound_dart_error_log_path
        from figma_flutter_agent.debug.terminal_log import bound_terminal_log_path
    
        terminal_log_path = bound_terminal_log_path()
        if terminal_log_path is not None and terminal_log_path.is_file():
            result.terminal_log = terminal_log_path.as_posix()
            run_log.info("Pipeline run log: {}", result.terminal_log)
        dart_errors_log = bound_dart_error_log_path()
        if dart_errors_log is not None and dart_errors_log.is_file():
            result.dart_errors_log = dart_errors_log.as_posix()
            run_log.info("Dart analyzer errors: {}", result.dart_errors_log)

        render_dir = bound_render_log_dir()
        if render_dir is not None and render_dir.is_dir():
            has_png = any(render_dir.glob("*.png"))
            if has_png:
                result.render_log_dir = render_dir.as_posix()
                run_log.info("Combat render captures: {}", result.render_log_dir)
    
        if settings.agent.dev.debug_capture:
            from figma_flutter_agent.debug.capture import run_project_debug_capture
    
            capture_outcome = await run_project_debug_capture(
                project_dir=project_dir,
                feature_name=ctx.resolved_feature,
                settings=settings,
                planned_files=planned_files,
                clean_tree=clean_tree,
                figma_reference_png=ctx.reference_image_png,
            )
            if capture_outcome is not None:
                result.debug_capture_dir = capture_outcome.capture_dir.as_posix()
                result.flutter_capture_ok = capture_outcome.flutter_capture_ok
                run_log.info("Debug capture artifacts: {}", result.debug_capture_dir)
                if not capture_outcome.flutter_capture_ok:
                    summary = "; ".join(capture_outcome.warnings[:2]) or "flutter render capture failed"
                    result.warnings.append(f"Flutter capture blocked: {summary}")
    
        if not dry_run and ctx.resolved_feature:
            from figma_flutter_agent.compiler.generation_config_fingerprint import (
                generation_config_fingerprint,
            )
            from figma_flutter_agent.debug.run_meta import write_run_meta

            _, cfg_hash = generation_config_fingerprint(settings)
            writeback = "committed" if result.written_files else "skipped"
            write_run_meta(
                project_dir,
                ctx.resolved_feature,
                pipeline_run_id=run_id,
                writeback=writeback,  # type: ignore[arg-type]
                written_files=result.written_files,
                committed_build_run_id=run_id if writeback == "committed" else None,
                cached_ir_verdict=ctx.cached_ir_verdict,
                clean_tree_hash=hashes.tree_hash,
                generation_config_hash=cfg_hash,
            )
            if pipeline_invocation != "repair_regenerate":
                from figma_flutter_agent.dev.opencode.run_gate import evaluate_run_gate

                evaluate_run_gate(project_dir, ctx.resolved_feature)

        return result

    try:
        return await _complete_run()
    except Exception as exc:
        fail_feature = ctx.resolved_feature or active_run_meta_feature or early_feature
        if active_run_meta_feature and fail_feature:
            from figma_flutter_agent.debug.run_meta import mark_run_meta_failed
            from figma_flutter_agent.errors import RunMetaStaleWriterError

            try:
                mark_run_meta_failed(
                    project_dir,
                    active_run_meta_feature,
                    pipeline_run_id=run_id,
                    error=str(exc),
                )
            except RunMetaStaleWriterError:
                log.debug(
                    "Skipping failed run.meta write for superseded pipeline run {}",
                    run_id,
                )
        raise


__all__ = ["run_pipeline"]

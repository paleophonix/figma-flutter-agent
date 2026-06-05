"""End-to-end generation pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids
from figma_flutter_agent.assets.webp import webp_conversion_available
from figma_flutter_agent.config import Settings
from figma_flutter_agent.dart_error_log import (
    bind_dart_error_session,
    bound_dart_error_log_path,
    update_dart_error_session,
)
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.figma.url import build_figma_url, parse_figma_url
from figma_flutter_agent.generator.planner import GenerationPlanContext
from figma_flutter_agent.generator.pubspec import read_pubspec_name
from figma_flutter_agent.observability import log_stage, new_run_id
from figma_flutter_agent.observability.llm_trace import bind_pipeline_observability
from figma_flutter_agent.parser.dedup import build_widget_extraction_hints
from figma_flutter_agent.parser.prototype import (
    build_navigation_hints,
    build_prototype_navigation_plan,
)
from figma_flutter_agent.pipeline.deps import (
    PipelineDependencies,
    default_pipeline_dependencies,
)
from figma_flutter_agent.pipeline.dump import (
    load_fetch_result_from_dump,
    resolve_frame_metadata_from_dump,
)
from figma_flutter_agent.pipeline.helpers import (
    enforce_emit_parse_gate,
    persist_planned_dart_debug_snapshot,
    resolve_feature_name,
    resolve_manifest_cached_dump,
    routing_enabled,
    validate_project_dir,
    validate_runtime_credentials,
)
from figma_flutter_agent.pipeline.incremental import (
    design_hashes,
    load_incremental_context,
    maybe_persist_snapshot,
    select_planned_writes,
)
from figma_flutter_agent.pipeline.llm import (
    append_llm_skip_warnings,
    ensure_llm_output_or_raise,
    execute_llm_stage,
    load_cached_ir_llm_outcome,
    warn_if_llm_screen_delegates_to_layout,
)
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.pipeline.warning_policy import skip_delegates_to_layout_warning
from figma_flutter_agent.pipeline_context import PipelineContext
from figma_flutter_agent.render_log import (
    bind_render_log_session,
    bound_render_log_dir,
    clear_render_log_session,
    render_log_enabled_for_pipeline,
    update_render_log_session,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    NodeType,
    merge_asset_manifests,
)
from figma_flutter_agent.stages import (
    LlmRepairStageRequest,
    PlanStageRequest,
    ValidateStageRequest,
    WriteStageRequest,
    export_figma_assets,
    fetch_figma_frame,
    parse_figma_frame,
    plan_generation_output,
    run_analyze_repair_loop,
    run_visual_refine_loop,
    validate_planned_generation,
)
from figma_flutter_agent.stages.assets import AssetExportRequest, finalize_screen_assets
from figma_flutter_agent.stages.fonts import FontExportRequest, export_fonts
from figma_flutter_agent.validation.reference import REFERENCE_DIR_NAME, resolve_figma_reference_png

__all__ = [
    "PipelineDependencies",
    "PipelineResult",
    "default_pipeline_dependencies",
    "format_dry_run_output",
    "run_pipeline",
]


@dataclass
class PipelineResult:
    """Output of a pipeline run."""

    clean_tree: CleanDesignTreeNode
    tokens: DesignTokens
    planned_files: list[str] = field(default_factory=list)
    written_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    run_id: str = ""
    clean_tree_hash: str = ""
    colors_hash: str = ""
    typography_hash: str = ""
    spacing_hash: str = ""
    dart_errors_log: str | None = None
    render_log_dir: str | None = None


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
) -> PipelineResult:
    """Execute the Figma to Flutter generation pipeline."""
    if verbose:
        logger.warning(
            "Verbose mode enabled: raw/processed design data will be dumped under "
            ".figma_debug/raw/ and .figma_debug/processed/. "
            "Ensure this directory is excluded from version control if it contains proprietary data."
        )

    validate_project_dir(project_dir)
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

    use_cached_ir = from_ir or from_ir_path is not None
    needs_figma_token = (
        require_figma_token if require_figma_token is not None else from_dump is None
    )
    validate_runtime_credentials(
        settings,
        dry_run=dry_run,
        require_figma_token=needs_figma_token,
        require_llm_api_key=not use_cached_ir
        and not settings.agent.generation.use_deterministic_screen,
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
    log = logger.bind(
        run_id=run_id,
        file_key=parsed.file_key,
        node_id=parsed.node_id,
        project_dir=str(project_dir),
        dry_run=dry_run,
        sync_enabled=resolved_sync,
    )
    log.info(
        "Generation mode: {} (llm_fallback_to_deterministic={})",
        "deterministic" if settings.agent.generation.use_deterministic_screen else "llm",
        settings.agent.generation.llm_fallback_to_deterministic,
    )
    log.info("Pipeline run started")
    if settings.agent.runtime.cleanup_stale_processes_on_start:
        from figma_flutter_agent.tools.stale_process_cleanup import cleanup_stale_agent_processes

        cleanup_stale_agent_processes()

    # ------------------------------------------------------------------
    # Dev Mode CSS dump (Phase 3) — load once, pass to every parse call.
    # ------------------------------------------------------------------
    _dev_mode_dump = None
    _dev_mode_css_override = False
    _figma_cfg = settings.agent.figma
    if (
        _figma_cfg.dev_mode.enabled
        and _figma_cfg.dev_mode.inspect_css.mode == "plugin_dump"
        and _figma_cfg.dev_mode.inspect_css.dump_path is not None
    ):
        from pathlib import Path as _Path

        from figma_flutter_agent.parser.dev_mode_css import (
            DevModeCssDumpError,
            load_dev_mode_css_dump,
        )

        _dump_path = _Path(_figma_cfg.dev_mode.inspect_css.dump_path)
        if not _dump_path.is_absolute():
            from figma_flutter_agent.config import agent_repo_root

            _dump_path = agent_repo_root() / _dump_path
        from figma_flutter_agent.pipeline.warning_policy import log_dev_mode_css_load_failure

        try:
            _dev_mode_dump = load_dev_mode_css_dump(_dump_path)
            _dev_mode_css_override = (
                _figma_cfg.style_metadata.source == "dev_mode_inspect"
            )
            log.info(
                "Dev Mode CSS dump loaded: {} ({} node(s))",
                _dump_path.name,
                len(_dev_mode_dump.nodes),
            )
        except DevModeCssDumpError as _exc:
            log_dev_mode_css_load_failure(
                log,
                settings=settings,
                style_source=_figma_cfg.style_metadata.source,
                exc=_exc,
            )

    if settings.agent.assets.webp and not webp_conversion_available():
        ctx.warnings.append(
            "WebP export is enabled (assets.webp) but Pillow is not installed; keeping PNG assets. "
            "Install with: poetry install (Pillow is a default dependency)."
        )

    if from_dump is not None:
        with log_stage(log, "fetch"):
            fetch_result = load_fetch_result_from_dump(
                from_dump,
                file_key=parsed.file_key,
                node_id=parsed.node_id,
            )
            ctx.apply_fetch(fetch_result)
            log.info("Loaded cached Figma dump from {}", from_dump.as_posix())
        with log_stage(log, "parse"):
            ctx.apply_parse(
                parse_figma_frame(
                    fetch_result,
                    dev_mode_dump=_dev_mode_dump,
                    dev_mode_css_override=_dev_mode_css_override,
                )
            )
            ctx.enforce_accessibility_gates()
            ctx.apply_accessibility_fixes()

        if not dry_run and ctx.clean_tree is not None:
            from figma_flutter_agent.parser.render_boundary import (
                collect_render_boundary_asset_plan,
                resolve_render_boundary_asset_keys,
            )
            from figma_flutter_agent.stages.assets import export_missing_render_boundary_assets

            destination_node_ids = {link.destination_node_id for link in ctx.prototype_links}
            exclude_node_ids = build_screen_frame_exclude_ids(parsed.node_id, destination_node_ids)
            raw_manifest = local_asset_manifest_from_project(
                project_dir,
                exclude_node_ids=exclude_node_ids,
            )
            ctx.asset_manifest, ctx.blocked_asset_paths = finalize_screen_assets(
                project_dir=project_dir,
                clean_tree=ctx.clean_tree,
                destination_trees=ctx.destination_trees,
                manifest=raw_manifest,
                primary_node_id=parsed.node_id,
                destination_node_ids=destination_node_ids,
            )
            boundary_exports, _flatten_excludes = collect_render_boundary_asset_plan(
                ctx.clean_tree,
            )
            unresolved = resolve_render_boundary_asset_keys(
                ctx.clean_tree,
                project_dir,
                ctx.asset_manifest,
                strict=settings.agent.assets.strict_render_boundary,
            )
            if unresolved and boundary_exports:
                try:
                    figma_token = settings.figma_token()
                except Exception:
                    figma_token = None
                if figma_token:
                    with log_stage(log, "assets"):
                        async with pipeline_deps.figma_connector(
                            figma_token,
                            settings.figma_api_base_url,
                        ) as connector:
                            boundary_manifest = await export_missing_render_boundary_assets(
                                connector,
                                file_key=parsed.file_key,
                                figma_root=ctx.figma_root,
                                project_dir=project_dir,
                                node_ids=frozenset(unresolved),
                                optimize_enabled=settings.agent.assets.optimize,
                            )
                            merge_asset_manifests(raw_manifest, boundary_manifest)
                            ctx.asset_manifest, ctx.blocked_asset_paths = finalize_screen_assets(
                                project_dir=project_dir,
                                clean_tree=ctx.clean_tree,
                                destination_trees=ctx.destination_trees,
                                manifest=raw_manifest,
                                primary_node_id=parsed.node_id,
                                destination_node_ids=destination_node_ids,
                            )
                else:
                    ctx.warnings.append(
                        "Render-boundary SVG(s) missing on disk and no Figma token; "
                        "use live sync or export assets before offline dump generation. "
                        f"Missing: {', '.join(unresolved)}"
                    )

            with log_stage(log, "fonts"):
                ctx.font_manifest = export_fonts(
                    FontExportRequest(
                        project_dir=project_dir,
                        clean_tree=ctx.clean_tree,
                        fonts=settings.agent.fonts,
                        destination_trees=ctx.destination_trees,
                    ),
                )
                ctx.warnings.extend(ctx.font_manifest.warnings)
    else:
        async with pipeline_deps.figma_connector(
            settings.figma_token(),
            settings.figma_api_base_url,
        ) as connector:
            with log_stage(log, "fetch"):
                fetch_result = await fetch_figma_frame(
                    connector,
                    file_key=parsed.file_key,
                    node_id=parsed.node_id,
                    project_dir=project_dir,
                    verbose=verbose,
                )
                ctx.apply_fetch(fetch_result)
            with log_stage(log, "parse"):
                ctx.apply_parse(
                    parse_figma_frame(
                        fetch_result,
                        dev_mode_dump=_dev_mode_dump,
                        dev_mode_css_override=_dev_mode_css_override,
                    )
                )
                ctx.enforce_accessibility_gates()
                ctx.apply_accessibility_fixes()

            if not dry_run and ctx.clean_tree is not None:
                with log_stage(log, "assets"):
                    from figma_flutter_agent.parser.render_boundary import (
                        collect_render_boundary_asset_plan,
                    )

                    destination_node_ids = {
                        link.destination_node_id for link in ctx.prototype_links
                    }
                    boundary_exports, flatten_excludes = collect_render_boundary_asset_plan(
                        ctx.clean_tree,
                    )
                    exported_manifest = await export_figma_assets(
                        connector,
                        AssetExportRequest(
                            file_key=parsed.file_key,
                            figma_root=ctx.figma_root,
                            project_dir=project_dir,
                            assets=settings.agent.assets,
                            prototype_links=ctx.prototype_links,
                            frame_index=fetch_result.frame_index,
                            primary_node_id=parsed.node_id,
                        ),
                        flatten_exclude_node_ids=flatten_excludes,
                        render_boundary_node_ids=boundary_exports,
                    )
                    ctx.asset_manifest, ctx.blocked_asset_paths = finalize_screen_assets(
                        project_dir=project_dir,
                        clean_tree=ctx.clean_tree,
                        destination_trees=ctx.destination_trees,
                        manifest=exported_manifest,
                        primary_node_id=parsed.node_id,
                        destination_node_ids=destination_node_ids,
                    )

                with log_stage(log, "fonts"):
                    ctx.font_manifest = export_fonts(
                        FontExportRequest(
                            project_dir=project_dir,
                            clean_tree=ctx.clean_tree,
                            fonts=settings.agent.fonts,
                            destination_trees=ctx.destination_trees,
                        ),
                    )
                    ctx.warnings.extend(ctx.font_manifest.warnings)

                attach_to_llm = (
                    not settings.agent.generation.use_deterministic_screen
                    and settings.agent.generation.llm_figma_reference_image
                )
                save_to_disk = settings.agent.validation.export_figma_reference
                if attach_to_llm or save_to_disk:
                    reference_feature = resolve_feature_name(
                        ctx.clean_tree.name,
                        feature_name or settings.agent.naming.feature_name,
                    )
                    resolution = await resolve_figma_reference_png(
                        connector=connector,
                        file_key=parsed.file_key,
                        node_id=parsed.node_id,
                        project_dir=project_dir,
                        feature_name=reference_feature,
                        figma_root=ctx.figma_root,
                        scale=settings.agent.validation.reference_scale,
                        attach_to_llm=attach_to_llm,
                        save_to_disk=save_to_disk,
                        from_dump=False,
                    )
                    ctx.reference_image_png = resolution.png_bytes
                    ctx.reference_image_hash = resolution.image_hash

    ctx.require_parse_complete()
    with log_stage(log, "analyze"):
        ctx.collect_analysis_warnings()

    clean_tree = ctx.clean_tree
    tokens = ctx.tokens
    dedup_result = ctx.dedup_result
    assert clean_tree is not None and tokens is not None and dedup_result is not None

    from figma_flutter_agent.generator.planner import _resolve_use_scaffold
    from figma_flutter_agent.parser.viewport_inset import (
        apply_viewport_top_inset_to_tree,
        compute_viewport_top_inset_px,
    )

    viewport_top_inset = compute_viewport_top_inset_px(
        settings,
        clean_tree,
        use_scaffold=_resolve_use_scaffold(settings, clean_tree),
    )
    if viewport_top_inset > 0:
        apply_viewport_top_inset_to_tree(clean_tree, viewport_top_inset)
        for destination_tree in ctx.destination_trees.values():
            apply_viewport_top_inset_to_tree(destination_tree, viewport_top_inset)

    configured_feature = feature_name or settings.agent.naming.feature_name
    ctx.resolved_feature = resolve_feature_name(clean_tree.name, configured_feature)
    update_dart_error_session(feature_name=ctx.resolved_feature)
    update_render_log_session(feature_name=ctx.resolved_feature)
    log = log.bind(feature_name=ctx.resolved_feature)
    if from_dump is not None:
        from figma_flutter_agent.parser.version import check_stale_processed_dump

        check_stale_processed_dump(
            project_dir,
            ctx.resolved_feature,
            strict=settings.agent.quality.enforce_spec9_gates,
        )

    if not dry_run and ctx.clean_tree is not None and ctx.tokens is not None:
        from figma_flutter_agent.debug.dumps import write_processed_dump, write_raw_dump

        write_processed_dump(
            project_dir,
            ctx.resolved_feature,
            clean_tree=ctx.clean_tree,
            tokens=ctx.tokens,
        )
        if verbose and ctx.figma_root:
            write_raw_dump(project_dir, ctx.resolved_feature, ctx.figma_root)

    hashes = design_hashes(clean_tree, tokens)
    incremental, sync_warnings = load_incremental_context(
        project_dir,
        settings,
        resolved_sync=resolved_sync,
        hashes=hashes,
    )
    ctx.warnings.extend(sync_warnings)

    routing_type = settings.agent.routing.type
    routing_on = routing_enabled(settings)
    navigation_plan = build_prototype_navigation_plan(
        ctx.resolved_feature,
        frame_index=ctx.frame_index,
        links=ctx.prototype_links,
        root_node_id=parsed.node_id,
    )
    from figma_flutter_agent.generator.navigation_codegen import build_route_transitions
    from figma_flutter_agent.parser.animations import collect_animation_suggestions

    route_transitions = (
        build_route_transitions(navigation_plan) if routing_on else {}
    )
    if settings.agent.ux.suggestions:
        animation_hints = collect_animation_suggestions(
            ctx.prototype_links,
            route_transitions=route_transitions or None,
        )
        ctx.warnings.extend(animation_hints)
    ctx.persist_optional_reports(
        feature_slug=ctx.resolved_feature,
        route_transitions=route_transitions or None,
        routing_type=routing_type,
    )
    navigation_hints = build_navigation_hints(navigation_plan) if routing_on else []
    widget_hints = build_widget_extraction_hints(dedup_result, ctx.cluster_summary)
    if not settings.agent.generation.use_deterministic_screen and clean_tree is not None:
        from figma_flutter_agent.generator.subtree_widgets import (
            build_subtree_widget_hints,
            collect_subtree_widget_specs,
        )

        subtree_specs = collect_subtree_widget_specs(
            clean_tree,
            widget_suffix=settings.agent.naming.widget_suffix,
        )
        widget_hints.extend(build_subtree_widget_hints(subtree_specs))
        if settings.agent.generation.true_subtree_pruning and subtree_specs:
            from figma_flutter_agent.generator.subtree_widgets import (
                replace_extracted_subtree_nodes_with_refs,
            )
            from figma_flutter_agent.parser.dedup import prune_generation_layout_tree

            replace_extracted_subtree_nodes_with_refs(clean_tree, subtree_specs)
            prune_generation_layout_tree(
                clean_tree,
                extracted_subtree_node_ids=frozenset(),
            )

    attach_to_llm = (
        not settings.agent.generation.use_deterministic_screen
        and settings.agent.generation.llm_figma_reference_image
    )
    needs_reference_png = (
        attach_to_llm
        or settings.agent.validation.export_figma_reference
        or settings.agent.generation.llm_visual_refine
    )
    if (
        not dry_run
        and from_dump is not None
        and needs_reference_png
        and ctx.reference_image_png is None
    ):
        resolution = await resolve_figma_reference_png(
            connector=None,
            file_key=parsed.file_key,
            node_id=parsed.node_id,
            project_dir=project_dir,
            feature_name=ctx.resolved_feature,
            figma_root=ctx.figma_root,
            scale=settings.agent.validation.reference_scale,
            attach_to_llm=attach_to_llm,
            save_to_disk=False,
            from_dump=True,
        )
        ctx.reference_image_png = resolution.png_bytes
        ctx.reference_image_hash = resolution.image_hash
        if ctx.reference_image_png is None and settings.figma_token():
            async with pipeline_deps.figma_connector(
                settings.figma_token(),
                settings.figma_api_base_url,
            ) as connector:
                resolution = await resolve_figma_reference_png(
                    connector=connector,
                    file_key=parsed.file_key,
                    node_id=parsed.node_id,
                    project_dir=project_dir,
                    feature_name=ctx.resolved_feature,
                    figma_root=ctx.figma_root,
                    scale=settings.agent.validation.reference_scale,
                    attach_to_llm=attach_to_llm,
                    save_to_disk=settings.agent.validation.export_figma_reference,
                    from_dump=False,
                )
            ctx.reference_image_png = resolution.png_bytes
            ctx.reference_image_hash = resolution.image_hash
            if ctx.reference_image_png is not None:
                log.info("Fetched Figma reference PNG in offline dump mode for visual QA/LLM")
        if ctx.reference_image_png is None:
            ctx.warnings.append(
                "Figma reference PNG missing in offline mode; "
                "run full/live generate once, or ensure FIGMA_ACCESS_TOKEN is set "
                f"to fetch reference into {REFERENCE_DIR_NAME}/."
            )

    with log_stage(log, "llm"):
        if use_cached_ir:
            llm_outcome = load_cached_ir_llm_outcome(
                log,
                settings=settings,
                project_dir=project_dir,
                resolved_feature=ctx.resolved_feature,
                clean_tree=clean_tree,
                tokens=tokens,
                from_ir_path=from_ir_path,
            )
        else:
            llm_outcome = await execute_llm_stage(
                log,
                settings=settings,
                dry_run=dry_run,
                resolved_sync=resolved_sync,
                incremental=incremental,
                clean_tree=clean_tree,
                tokens=tokens,
                resolved_feature=ctx.resolved_feature,
                asset_manifest=ctx.asset_manifest,
                widget_hints=widget_hints,
                navigation_hints=navigation_hints,
                routing_on=routing_on,
                navigation_plan=navigation_plan,
                frame_index=ctx.frame_index,
                published_styles=ctx.published_styles,
                components=ctx.components,
                component_sets=ctx.component_sets,
                destination_trees=ctx.destination_trees,
                destination_widget_hints=ctx.destination_widget_hints,
                style_paint_index=ctx.style_paint_index,
                force_llm_regen=force_llm_regen,
                llm_client_factory=pipeline_deps.create_llm_client,
                figma_reference_png=ctx.reference_image_png,
                project_dir=project_dir,
            )
    ctx.warnings.extend(llm_outcome.llm_result.warnings)
    ctx.warnings.extend(llm_outcome.fallback_warnings)

    with log_stage(log, "plan"):
        planned_files = plan_generation_output(
            PlanStageRequest(
                context=GenerationPlanContext(
                    settings=llm_outcome.plan_settings,
                    clean_tree=clean_tree,
                    tokens=tokens,
                    resolved_feature=ctx.resolved_feature,
                    node_id=parsed.node_id,
                    cluster_summary=ctx.cluster_summary,
                    asset_manifest=ctx.asset_manifest,
                    font_manifest=ctx.font_manifest,
                    generation=llm_outcome.llm_result.generation,
                    destination_generations=llm_outcome.llm_result.destination_generations,
                    destination_trees=ctx.destination_trees,
                    navigation_plan=navigation_plan,
                    figma_root=ctx.figma_root,
                    routing_on=routing_on,
                    package_name=read_pubspec_name(project_dir),
                    blocked_asset_paths=ctx.blocked_asset_paths,
                    project_dir=project_dir,
                ),
            ),
        ).planned_files

    package_name = read_pubspec_name(project_dir)
    architecture = settings.agent.flutter.architecture

    def _persist_dart_debug_bug(files: dict[str, str]) -> None:
        persist_planned_dart_debug_snapshot(
            project_dir,
            feature_name=ctx.resolved_feature,
            planned_files=files,
            package_name=package_name,
            architecture=architecture,
            snapshot="bug",
        )

    persist_planned_dart_debug_snapshot(
        project_dir,
        feature_name=ctx.resolved_feature,
        planned_files=planned_files,
        package_name=package_name,
        architecture=architecture,
        snapshot="plan",
    )
    if settings.agent.ux.design_coverage and ctx.clean_tree is not None:
        from figma_flutter_agent.parser.design_coverage import write_design_coverage_report

        write_design_coverage_report(
            project_dir,
            feature_slug=ctx.resolved_feature,
            root=ctx.clean_tree,
            planned_dart=planned_files,
        )

    enforce_emit_parse_gate(
        settings,
        planned_files,
        package_name=package_name,
        stage="post_plan_parse_gate",
        typography_tokens=tokens,
        clean_tree=clean_tree,
        on_parse_gate_failure=_persist_dart_debug_bug,
    )

    warn_if_llm_screen_delegates_to_layout(
        ctx.warnings,
        planned_files=planned_files,
        feature_name=ctx.resolved_feature,
        use_deterministic_screen=llm_outcome.use_deterministic_screen,
        architecture=settings.agent.flutter.architecture,
        skip_when_expected=skip_delegates_to_layout_warning(
            settings=settings,
            use_cached_ir=use_cached_ir,
        ),
    )

    has_overlay_links = any(link.navigation_kind == "overlay" for link in navigation_plan.links)
    responsive_shell_required = settings.agent.responsive.enabled
    with log_stage(log, "validate"):
        validate_result = validate_planned_generation(
            ValidateStageRequest(
                planned_files=planned_files,
                clean_trees=[clean_tree, *ctx.destination_trees.values()],
                responsive_enabled=settings.agent.responsive.enabled,
                avoid_fixed_sizes=settings.agent.layout.avoid_fixed_sizes,
                require_overlay_helpers=has_overlay_links,
                strict_accessibility_labels=settings.agent.quality.strict_accessibility_labels,
                cluster_summary=ctx.cluster_summary,
                cluster_min_count=settings.agent.generation.cluster_min_count,
                widget_suffix=settings.agent.naming.widget_suffix,
                enforce_cluster_widgets=settings.agent.generation.enforce_cluster_widgets,
                fail_duplicate_clusters=settings.agent.quality.fail_duplicate_clusters,
                require_responsive_shell=responsive_shell_required,
                use_deterministic_screen=llm_outcome.use_deterministic_screen,
            ),
        )
    ctx.warnings.extend(validate_result.warnings)
    append_llm_skip_warnings(
        ctx.warnings,
        llm_result=llm_outcome.llm_result,
        tokens_changed=incremental.tokens_changed,
    )

    with log_stage(log, "llm_repair"):
        post_gen_request = LlmRepairStageRequest(
            settings=settings,
            dry_run=dry_run,
            project_dir=project_dir,
            planned_files=planned_files,
            llm_result=llm_outcome.llm_result,
            use_deterministic_screen=llm_outcome.use_deterministic_screen,
            clean_tree=clean_tree,
            tokens=tokens,
            resolved_feature=ctx.resolved_feature,
            node_id=parsed.node_id,
            cluster_summary=ctx.cluster_summary,
            asset_manifest=ctx.asset_manifest,
            font_manifest=ctx.font_manifest,
            widget_hints=widget_hints,
            navigation_hints=navigation_hints,
            routing_on=routing_on,
            navigation_plan=navigation_plan,
            figma_root=ctx.figma_root,
            package_name=read_pubspec_name(project_dir),
            blocked_asset_paths=ctx.blocked_asset_paths,
            destination_trees=ctx.destination_trees,
            llm_client_factory=pipeline_deps.create_llm_repair_client,
            figma_reference_png=ctx.reference_image_png,
        )
        repair_outcome = await run_analyze_repair_loop(post_gen_request)
    planned_files = repair_outcome.planned_files
    ctx.warnings.extend(repair_outcome.warnings)

    with log_stage(log, "llm_visual_refine"):
        visual_outcome = await run_visual_refine_loop(
            post_gen_request,
            planned_files=planned_files,
            llm_client_factory=pipeline_deps.create_llm_refine_client,
        )
    planned_files = visual_outcome.planned_files
    ctx.warnings.extend(visual_outcome.warnings)

    persist_planned_dart_debug_snapshot(
        project_dir,
        feature_name=ctx.resolved_feature,
        planned_files=planned_files,
        package_name=package_name,
        architecture=architecture,
        snapshot="final",
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

    ensure_llm_output_or_raise(
        llm_result=llm_outcome.llm_result,
        tree_changed=incremental.tree_changed,
        use_deterministic_screen=llm_outcome.use_deterministic_screen,
        llm_fallback_applied=llm_outcome.llm_fallback_applied,
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
            not llm_outcome.use_deterministic_screen
            and llm_outcome.llm_result.generation is not None
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
            on_parse_gate_failure=_persist_dart_debug_bug,
        )
    if files_to_write and settings.agent.validation.spec23_dart_analyze:
        from figma_flutter_agent.errors import GenerationError
        from figma_flutter_agent.generator.validation import analyze_planned_dart_files

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

    if files_to_write:
        with log_stage(log, "write"):
            write_result = pipeline_deps.commit_planned_files(
                WriteStageRequest(
                    project_dir=project_dir,
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
                    on_parse_gate_failure=_persist_dart_debug_bug,
                ),
            )
        result.written_files = write_result.written_files
    else:
        log.info("Incremental sync: no files required updates")

    maybe_persist_snapshot(
        log,
        project_dir=project_dir,
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

    dart_log = bound_dart_error_log_path()
    if dart_log is not None and dart_log.is_file():
        result.dart_errors_log = dart_log.as_posix()
        log.info("Dart analyzer session log: {}", result.dart_errors_log)

    render_dir = bound_render_log_dir()
    if render_dir is not None and render_dir.is_dir():
        has_png = any(render_dir.glob("*.png"))
        if has_png:
            result.render_log_dir = render_dir.as_posix()
            log.info("Combat render captures: {}", result.render_log_dir)

    if not dry_run:
        from figma_flutter_agent.debug.mirror import sync_figma_debug_tree

        mirrored = sync_figma_debug_tree(project_dir)
        if mirrored:
            log.info(
                "Figma debug mirror: {} file(s) under logs/figma-debug/",
                len(mirrored),
            )

    return result


def format_dry_run_output(result: PipelineResult, *, include_design: bool = False) -> str:
    """Format dry-run output for CLI display."""
    payload: dict[str, object] = {
        "warnings": result.warnings,
        "plannedFiles": result.planned_files,
        "summary": {
            "runId": result.run_id,
            "plannedFileCount": len(result.planned_files),
            "cleanTreeHash": result.clean_tree_hash,
            "colorsHash": result.colors_hash,
            "typographyHash": result.typography_hash,
            "spacingHash": result.spacing_hash,
            "tokenCounts": {
                "colors": len(result.tokens.colors),
                "typography": len(result.tokens.typography),
                "spacing": len(result.tokens.spacing),
                "radii": len(result.tokens.radii),
                "elevations": len(result.tokens.elevations),
            },
        },
    }
    if include_design:
        from figma_flutter_agent.llm.payload_slim import (
            dump_clean_tree_for_llm,
            dump_tokens_for_llm,
        )

        payload["cleanTree"] = dump_clean_tree_for_llm(result.clean_tree)
        payload["tokens"] = dump_tokens_for_llm(result.tokens)
    return json.dumps(payload, indent=2, ensure_ascii=False)

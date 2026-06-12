"""Stage-execution helper functions extracted from ``pipeline.run.core``.

These helpers encapsulate the fetch/parse/asset/font and post-parse
preparation phases of :func:`figma_flutter_agent.pipeline.run.core.run_pipeline`.
They mutate the shared :class:`PipelineContext` in place and return any
additional values the caller needs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids
from figma_flutter_agent.config import Settings
from figma_flutter_agent.dart_error_log import update_dart_error_session
from figma_flutter_agent.figma.url import ParsedFigmaUrl
from figma_flutter_agent.observability import log_stage
from figma_flutter_agent.pipeline.deps import PipelineDependencies
from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump
from figma_flutter_agent.pipeline.helpers import resolve_feature_name
from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
from figma_flutter_agent.pipeline_context import PipelineContext
from figma_flutter_agent.render_log import update_render_log_session
from figma_flutter_agent.schemas import merge_asset_manifests
from figma_flutter_agent.stages.assets import AssetExportRequest, finalize_screen_assets
from figma_flutter_agent.stages.fonts import FontExportRequest, export_fonts
from figma_flutter_agent.validation.reference import resolve_figma_reference_png


async def run_dump_fetch_parse_phase(
    ctx: PipelineContext,
    *,
    log: Any,
    parsed: ParsedFigmaUrl,
    settings: Settings,
    project_dir: Path,
    from_dump: Path,
    dry_run: bool,
    offline_dump_mode: bool,
    pipeline_deps: PipelineDependencies,
    dev_mode_dump: Any,
    dev_mode_css_override: Any,
    parse_fn: Any,
) -> None:
    """Fetch, parse, and export assets/fonts when running from a cached dump.

    Args:
        ctx: Shared pipeline context, mutated in place.
        log: Bound logger for this run.
        parsed: Parsed Figma URL (file key / node id).
        settings: Resolved agent settings.
        project_dir: Target Flutter project directory.
        from_dump: Path to the cached raw layout dump.
        dry_run: Whether the pipeline is running in dry-run mode.
        offline_dump_mode: Whether live Figma fetches are disallowed.
        pipeline_deps: Injected pipeline dependencies (connector factory, etc.).
        dev_mode_dump: Optional Dev Mode CSS dump payload.
        dev_mode_css_override: Optional Dev Mode CSS override payload.
        parse_fn: The ``parse_figma_frame`` callable (passed through so test
            patches on ``pipeline.run.core.parse_figma_frame`` take effect).
    """
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
            parse_fn(
                fetch_result,
                dev_mode_dump=dev_mode_dump,
                dev_mode_css_override=dev_mode_css_override,
            )
        )
        ctx.enforce_accessibility_gates()
        ctx.apply_accessibility_fixes()

    if dry_run or ctx.clean_tree is None:
        return

    from figma_flutter_agent.parser.boundaries.assets import (
        collect_render_boundary_asset_plan,
        resolve_missing_image_asset_keys,
        resolve_render_boundary_asset_keys,
    )
    from figma_flutter_agent.stages.assets import export_missing_render_boundary_assets

    destination_node_ids = {link.destination_node_id for link in ctx.prototype_links}
    exclude_node_ids = build_screen_frame_exclude_ids(parsed.node_id, destination_node_ids)
    raw_manifest = local_asset_manifest_from_project(
        project_dir,
        exclude_node_ids=exclude_node_ids,
        clean_tree=ctx.clean_tree,
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

    resolve_missing_image_asset_keys(ctx.clean_tree, project_dir)
    if unresolved and boundary_exports:
        try:
            figma_token = settings.figma_token()
        except Exception:
            figma_token = None
        if figma_token and not offline_dump_mode:
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
        elif unresolved:
            if offline_dump_mode:
                ctx.warnings.append(
                    "Render-boundary SVG(s) missing on disk (offline mode; no live export). "
                    "Run fetch/full sync once or export assets before offline runs. "
                    f"Missing: {', '.join(unresolved)}"
                )
            else:
                ctx.warnings.append(
                    "Render-boundary SVG(s) missing on disk and no Figma token; "
                    "use live sync or export assets before offline dump generation. "
                    f"Missing: {', '.join(unresolved)}"
                )

    if not offline_dump_mode:
        try:
            figma_token = settings.figma_token()
        except Exception:
            figma_token = None
        if figma_token:
            from figma_flutter_agent.assets.exporter import AssetExporter

            with log_stage(log, "assets"):
                async with pipeline_deps.figma_connector(
                    figma_token,
                    settings.figma_api_base_url,
                ) as connector:
                    exporter = AssetExporter(connector)
                    outcome = await exporter.export_assets(
                        parsed.file_key,
                        ctx.figma_root,
                        project_dir,
                        svg_enabled=settings.agent.assets.svg,
                        raster_enabled=True,
                        blur_png_fallback=True,
                        png_scales=settings.agent.assets.png_scales,
                        webp_enabled=settings.agent.assets.webp,
                        illustrations_enabled=settings.agent.assets.illustrations,
                        optimize_enabled=settings.agent.assets.optimize,
                        continue_on_rate_limit=True,
                        inter_batch_delay_sec=settings.agent.assets.images_batch_delay_sec,
                        skip_existing_assets=True,
                        exclude_node_ids=set(exclude_node_ids),
                        flatten_exclude_node_ids=set(_flatten_excludes),
                        render_boundary_node_ids=set(boundary_exports),
                    )
                    if outcome.manifest.entries:
                        merge_asset_manifests(raw_manifest, outcome.manifest)
                        ctx.asset_manifest, ctx.blocked_asset_paths = finalize_screen_assets(
                            project_dir=project_dir,
                            clean_tree=ctx.clean_tree,
                            destination_trees=ctx.destination_trees,
                            manifest=raw_manifest,
                            primary_node_id=parsed.node_id,
                            destination_node_ids=destination_node_ids,
                        )
                    if outcome.failed_node_ids:
                        ctx.warnings.append(
                            "Asset export could not fetch "
                            f"{len(outcome.failed_node_ids)} node(s) from Figma Images API."
                        )
                    if outcome.rate_limited:
                        ctx.warnings.append(
                            "Asset export hit Figma rate limits; retry list → assets later."
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


async def run_live_fetch_parse_phase(
    ctx: PipelineContext,
    *,
    log: Any,
    parsed: ParsedFigmaUrl,
    settings: Settings,
    project_dir: Path,
    dry_run: bool,
    verbose: bool,
    pipeline_deps: PipelineDependencies,
    dev_mode_dump: Any,
    dev_mode_css_override: Any,
    parse_fn: Any,
    fetch_fn: Any,
    export_assets_fn: Any,
) -> None:
    """Fetch, parse, and export assets/fonts/reference PNG via the live Figma API.

    Args:
        ctx: Shared pipeline context, mutated in place.
        log: Bound logger for this run.
        parsed: Parsed Figma URL (file key / node id).
        settings: Resolved agent settings.
        project_dir: Target Flutter project directory.
        dry_run: Whether the pipeline is running in dry-run mode.
        verbose: Whether verbose debug dumps are enabled.
        pipeline_deps: Injected pipeline dependencies (connector factory, etc.).
        dev_mode_dump: Optional Dev Mode CSS dump payload.
        dev_mode_css_override: Optional Dev Mode CSS override payload.
        parse_fn: The ``parse_figma_frame`` callable (passed through so test
            patches on ``pipeline.run.core.parse_figma_frame`` take effect).
        fetch_fn: The ``fetch_figma_frame`` callable (passed through for patching).
        export_assets_fn: The ``export_figma_assets`` callable (passed through for patching).
    """
    async with pipeline_deps.figma_connector(
        settings.figma_token(),
        settings.figma_api_base_url,
    ) as connector:
        with log_stage(log, "fetch"):
            fetch_result = await fetch_fn(
                connector,
                file_key=parsed.file_key,
                node_id=parsed.node_id,
                project_dir=project_dir,
                verbose=verbose,
            )
            ctx.apply_fetch(fetch_result)
        with log_stage(log, "parse"):
            ctx.apply_parse(
                parse_fn(
                    fetch_result,
                    dev_mode_dump=dev_mode_dump,
                    dev_mode_css_override=dev_mode_css_override,
                )
            )
            ctx.enforce_accessibility_gates()
            ctx.apply_accessibility_fixes()

        if dry_run or ctx.clean_tree is None:
            return

        with log_stage(log, "assets"):
            from figma_flutter_agent.parser.boundaries.assets import (
                collect_render_boundary_asset_plan,
            )

            destination_node_ids = {link.destination_node_id for link in ctx.prototype_links}
            boundary_exports, flatten_excludes = collect_render_boundary_asset_plan(
                ctx.clean_tree,
            )
            exported_manifest = await export_assets_fn(
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

        attach_to_llm = settings.agent.generation.llm_figma_reference_image
        save_to_disk = (
            settings.agent.validation.export_figma_reference
            or settings.agent.dev.debug_capture
        )
        if attach_to_llm or save_to_disk:
            reference_feature = resolve_feature_name(
                ctx.clean_tree.name,
                ctx.feature_name or settings.agent.naming.feature_name,
            )
            with log_stage(log, "reference"):
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


async def resolve_offline_reference_png(
    ctx: PipelineContext,
    *,
    log: Any,
    parsed: ParsedFigmaUrl,
    settings: Settings,
    project_dir: Path,
    offline_dump_mode: bool,
    pipeline_deps: PipelineDependencies,
) -> None:
    """Resolve a Figma reference PNG when running from an offline dump.

    Args:
        ctx: Shared pipeline context, mutated in place.
        log: Bound logger for this run.
        parsed: Parsed Figma URL (file key / node id).
        settings: Resolved agent settings.
        project_dir: Target Flutter project directory.
        offline_dump_mode: Whether live Figma fetches are disallowed.
        pipeline_deps: Injected pipeline dependencies (connector factory, etc.).
    """
    attach_to_llm = settings.agent.generation.llm_figma_reference_image
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
    if ctx.reference_image_png is None and settings.figma_token() and not offline_dump_mode:
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
                save_to_disk=(
                    settings.agent.validation.export_figma_reference
                    or settings.agent.dev.debug_capture
                ),
                from_dump=False,
            )
        ctx.reference_image_png = resolution.png_bytes
        ctx.reference_image_hash = resolution.image_hash
        if ctx.reference_image_png is not None:
            log.info("Fetched Figma reference PNG for visual QA/LLM")
    if ctx.reference_image_png is None:
        from figma_flutter_agent.validation.reference import REFERENCE_DIR_NAME

        ctx.warnings.append(
            "Figma reference PNG missing in offline mode; "
            "run wizard run → full once to cache it under "
            f"{REFERENCE_DIR_NAME}/, or disable llm_figma_reference_image."
        )


def apply_viewport_inset_and_resolve_feature(
    ctx: PipelineContext,
    *,
    log: Any,
    settings: Settings,
    project_dir: Path,
    feature_name: str | None,
    from_dump: Path | None,
    dry_run: bool,
    verbose: bool,
) -> Any:
    """Apply the viewport top inset, resolve the feature slug, and write debug dumps.

    Args:
        ctx: Shared pipeline context, mutated in place.
        log: Bound logger for this run (rebound with ``feature_name``).
        settings: Resolved agent settings.
        project_dir: Target Flutter project directory.
        feature_name: User-supplied feature name override, if any.
        from_dump: Path to the cached raw layout dump, if running offline.
        dry_run: Whether the pipeline is running in dry-run mode.
        verbose: Whether verbose debug dumps are enabled.

    Returns:
        The logger rebound with ``feature_name``.
    """
    from figma_flutter_agent.generator.planner import _resolve_use_scaffold
    from figma_flutter_agent.parser.viewport_inset import (
        apply_viewport_top_inset_to_tree,
        compute_viewport_top_inset_px,
    )

    clean_tree = ctx.clean_tree
    assert clean_tree is not None

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
    from figma_flutter_agent.debug.provenance import activate_provenance_recorder

    activate_provenance_recorder(
        feature_name=ctx.resolved_feature,
        project_dir=project_dir,
    )
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

    return log


def prepare_navigation_and_subtree(
    ctx: PipelineContext,
    *,
    settings: Settings,
    parsed: ParsedFigmaUrl,
    routing_on: bool,
) -> tuple[Any, dict[str, Any], list[str], list[str]]:
    """Build the prototype navigation plan and subtree/widget extraction hints.

    Args:
        ctx: Shared pipeline context (read-only here).
        settings: Resolved agent settings.
        parsed: Parsed Figma URL (file key / node id).
        routing_on: Whether routing/navigation generation is enabled.

    Returns:
        A tuple of ``(navigation_plan, route_transitions, navigation_hints)``
        plus mutates ``ctx.warnings`` with animation suggestions.
    """
    from figma_flutter_agent.generator.navigation_codegen import build_route_transitions
    from figma_flutter_agent.parser.animations import collect_animation_suggestions
    from figma_flutter_agent.parser.dedup.hints import build_widget_extraction_hints
    from figma_flutter_agent.parser.prototype import (
        build_navigation_hints,
        build_prototype_navigation_plan,
    )

    navigation_plan = build_prototype_navigation_plan(
        ctx.resolved_feature,
        frame_index=ctx.frame_index,
        links=ctx.prototype_links,
        root_node_id=parsed.node_id,
    )
    route_transitions = build_route_transitions(navigation_plan) if routing_on else {}
    if settings.agent.ux.suggestions:
        animation_hints = collect_animation_suggestions(
            ctx.prototype_links,
            route_transitions=route_transitions or None,
        )
        ctx.warnings.extend(animation_hints)

    navigation_hints = build_navigation_hints(navigation_plan) if routing_on else []
    widget_hints = build_widget_extraction_hints(ctx.dedup_result, ctx.cluster_summary)
    if ctx.clean_tree is not None:
        from figma_flutter_agent.generator.subtree import (
            build_subtree_widget_hints,
            collect_subtree_widget_specs,
        )

        subtree_specs = collect_subtree_widget_specs(
            ctx.clean_tree,
            widget_suffix=settings.agent.naming.widget_suffix,
        )
        widget_hints.extend(build_subtree_widget_hints(subtree_specs))
        if settings.agent.generation.true_subtree_pruning and subtree_specs:
            from figma_flutter_agent.generator.subtree import (
                replace_extracted_subtree_nodes_with_refs,
            )
            from figma_flutter_agent.parser.dedup.prune import prune_generation_layout_tree

            replace_extracted_subtree_nodes_with_refs(ctx.clean_tree, subtree_specs)
            prune_generation_layout_tree(
                ctx.clean_tree,
                extracted_subtree_node_ids=frozenset(),
            )

    return navigation_plan, route_transitions, navigation_hints, widget_hints


async def run_llm_and_plan_phase(
    ctx: PipelineContext,
    *,
    log: Any,
    settings: Settings,
    parsed: ParsedFigmaUrl,
    project_dir: Path,
    dry_run: bool,
    resolved_sync: bool,
    incremental: Any,
    clean_tree: Any,
    tokens: Any,
    navigation_plan: Any,
    navigation_hints: list[str],
    widget_hints: list[str],
    routing_on: bool,
    use_cached_ir: bool,
    from_ir_path: Path | None,
    force_llm_regen: bool,
    pipeline_deps: PipelineDependencies,
    execute_llm_stage_fn: Any,
) -> tuple[Any, dict[str, str]]:
    """Run the LLM generation stage and the deterministic planner stage.

    Args:
        ctx: Shared pipeline context, mutated with warnings.
        log: Bound logger for this run.
        settings: Resolved agent settings.
        parsed: Parsed Figma URL (file key / node id).
        project_dir: Target Flutter project directory.
        dry_run: Whether the pipeline is running in dry-run mode.
        resolved_sync: Whether incremental sync is enabled.
        incremental: Loaded incremental sync context.
        clean_tree: Root clean design tree node.
        tokens: Extracted design tokens.
        navigation_plan: Prototype navigation plan.
        navigation_hints: Navigation hint strings for the LLM prompt.
        widget_hints: Widget extraction hint strings for the LLM prompt.
        routing_on: Whether routing/navigation generation is enabled.
        use_cached_ir: Whether to load a cached IR instead of calling the LLM.
        from_ir_path: Optional explicit path to a cached IR file.
        force_llm_regen: Whether to bypass incremental LLM caching.
        pipeline_deps: Injected pipeline dependencies (LLM client factories, etc.).
        execute_llm_stage_fn: The ``execute_llm_stage`` callable (passed through so test
            patches on ``pipeline.run.core.execute_llm_stage`` take effect).

    Returns:
        A tuple of ``(llm_outcome, planned_files)``.
    """
    from figma_flutter_agent.generator.planner import GenerationPlanContext
    from figma_flutter_agent.generator.pubspec import read_pubspec_name
    from figma_flutter_agent.pipeline.llm import load_cached_ir_llm_outcome
    from figma_flutter_agent.stages import PlanStageRequest, plan_generation_output

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
            llm_outcome = await execute_llm_stage_fn(
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

    return llm_outcome, planned_files


async def run_validate_repair_refine_phase(
    ctx: PipelineContext,
    *,
    log: Any,
    settings: Settings,
    parsed: ParsedFigmaUrl,
    project_dir: Path,
    dry_run: bool,
    clean_tree: Any,
    tokens: Any,
    incremental: Any,
    navigation_plan: Any,
    navigation_hints: list[str],
    widget_hints: list[str],
    routing_on: bool,
    use_cached_ir: bool,
    llm_outcome: Any,
    planned_files: dict[str, str],
    package_name: str,
    architecture: Any,
    pipeline_deps: PipelineDependencies,
    run_analyze_repair_loop_fn: Any,
) -> tuple[dict[str, str], Any]:
    """Run the parse gate, validation, LLM repair, and visual-refine stages.

    Args:
        ctx: Shared pipeline context, mutated with warnings.
        log: Bound logger for this run.
        settings: Resolved agent settings.
        parsed: Parsed Figma URL (file key / node id).
        project_dir: Target Flutter project directory.
        dry_run: Whether the pipeline is running in dry-run mode.
        clean_tree: Root clean design tree node.
        tokens: Extracted design tokens.
        incremental: Loaded incremental sync context.
        navigation_plan: Prototype navigation plan.
        navigation_hints: Navigation hint strings.
        widget_hints: Widget extraction hint strings.
        routing_on: Whether routing/navigation generation is enabled.
        use_cached_ir: Whether a cached IR was used for the LLM stage.
        llm_outcome: Outcome of the LLM generation stage.
        planned_files: Planner output map of relative path to Dart source.
        package_name: Resolved Flutter package name.
        architecture: Configured Flutter architecture setting.
        pipeline_deps: Injected pipeline dependencies (LLM client factories, etc.).
        run_analyze_repair_loop_fn: The ``run_analyze_repair_loop`` callable (passed
            through so test patches on ``pipeline.run.core.run_analyze_repair_loop``
            take effect).

    Returns:
        A tuple of ``(planned_files, post_gen_request)`` after repair/refine.
    """
    from figma_flutter_agent.pipeline.helpers import (
        enforce_emit_parse_gate,
        persist_planned_dart_debug_snapshot,
    )
    from figma_flutter_agent.pipeline.llm import (
        append_llm_skip_warnings,
        warn_if_llm_screen_delegates_to_layout,
    )
    from figma_flutter_agent.pipeline.warning_policy import skip_delegates_to_layout_warning
    from figma_flutter_agent.stages import (
        LlmRepairStageRequest,
        ValidateStageRequest,
        run_visual_refine_loop,
        validate_planned_generation,
    )

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
        feature_name=ctx.resolved_feature,
        routing_on=routing_on,
        on_parse_gate_failure=_persist_dart_debug_bug,
    )

    warn_if_llm_screen_delegates_to_layout(
        ctx.warnings,
        planned_files=planned_files,
        feature_name=ctx.resolved_feature,
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
            ),
        )
    ctx.warnings.extend(validate_result.warnings)
    append_llm_skip_warnings(
        ctx.warnings,
        llm_result=llm_outcome.llm_result,
        tokens_changed=incremental.tokens_changed,
    )

    from figma_flutter_agent.generator.pubspec import read_pubspec_name

    with log_stage(log, "llm_repair"):
        post_gen_request = LlmRepairStageRequest(
            settings=settings,
            dry_run=dry_run,
            project_dir=project_dir,
            planned_files=planned_files,
            llm_result=llm_outcome.llm_result,
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
        repair_outcome = await run_analyze_repair_loop_fn(post_gen_request)
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

    return planned_files, post_gen_request


__all__ = [
    "run_dump_fetch_parse_phase",
    "run_live_fetch_parse_phase",
    "resolve_offline_reference_png",
    "apply_viewport_inset_and_resolve_feature",
    "prepare_navigation_and_subtree",
    "run_llm_and_plan_phase",
    "run_validate_repair_refine_phase",
]

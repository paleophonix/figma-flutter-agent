"""Fetch, parse, assets, and fonts pipeline phases."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from figma_flutter_agent.config import Settings
    from figma_flutter_agent.pipeline.deps import PipelineDependencies
    from figma_flutter_agent.pipeline_context import PipelineContext
    from figma_flutter_agent.schemas import FigmaParsedUrl


async def load_dev_mode_css(
    settings: Settings,
    log: logger,
) -> tuple[object | None, bool]:
    """Load Dev Mode CSS dump if configured.

    Args:
        settings: Pipeline settings.
        log: Bound logger instance.

    Returns:
        Tuple of (dev_mode_dump, dev_mode_css_override).
    """
    _figma_cfg = settings.agent.figma
    if not (
        _figma_cfg.dev_mode.enabled
        and _figma_cfg.dev_mode.inspect_css.mode == "plugin_dump"
        and _figma_cfg.dev_mode.inspect_css.dump_path is not None
    ):
        return None, False

    from figma_flutter_agent.parser.dev_mode_css import (
        DevModeCssDumpError,
        load_dev_mode_css_dump,
    )
    from figma_flutter_agent.pipeline.warning_policy import log_dev_mode_css_load_failure

    _dump_path = Path(_figma_cfg.dev_mode.inspect_css.dump_path)
    if not _dump_path.is_absolute():
        from figma_flutter_agent.config import agent_repo_root

        _dump_path = agent_repo_root() / _dump_path

    try:
        dev_mode_dump = load_dev_mode_css_dump(_dump_path)
        dev_mode_css_override = _figma_cfg.style_metadata.source == "dev_mode_inspect"
        log.info(
            "Dev Mode CSS dump loaded: {} ({} node(s))",
            _dump_path.name,
            len(dev_mode_dump.nodes),
        )
        return dev_mode_dump, dev_mode_css_override
    except DevModeCssDumpError as _exc:
        log_dev_mode_css_load_failure(
            log,
            settings=settings,
            style_source=_figma_cfg.style_metadata.source,
            exc=_exc,
        )
        return None, False


async def run_fetch_parse_offline(
    ctx: PipelineContext,
    *,
    from_dump: Path,
    parsed: FigmaParsedUrl,
    settings: Settings,
    pipeline_deps: PipelineDependencies,
    log: logger,
    dev_mode_dump: object | None,
    dev_mode_css_override: bool,
    offline_dump_mode: bool,
) -> None:
    """Execute fetch+parse+assets+fonts stages from a cached dump.

    Args:
        ctx: Mutable pipeline context.
        from_dump: Path to the cached dump file.
        parsed: Parsed Figma URL components.
        settings: Pipeline settings.
        pipeline_deps: Injectable pipeline dependencies.
        log: Bound logger instance.
        dev_mode_dump: Optional Dev Mode CSS dump.
        dev_mode_css_override: Whether Dev Mode CSS overrides style source.
        offline_dump_mode: Whether running in fully offline mode.
    """
    from figma_flutter_agent.observability import log_stage
    from figma_flutter_agent.parser.prototype import build_navigation_hints  # noqa: F401
    from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump
    from figma_flutter_agent.stages import parse_figma_frame
    from figma_flutter_agent.stages.fonts import FontExportRequest, export_fonts

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
                dev_mode_dump=dev_mode_dump,
                dev_mode_css_override=dev_mode_css_override,
            )
        )
        ctx.enforce_accessibility_gates()
        ctx.apply_accessibility_fixes()

    if not ctx.dry_run and ctx.clean_tree is not None:
        from figma_flutter_agent.assets.screen_frame import build_screen_frame_exclude_ids
        from figma_flutter_agent.parser.boundaries.assets import (
            collect_render_boundary_asset_plan,
            resolve_render_boundary_asset_keys,
        )
        from figma_flutter_agent.pipeline.local_assets import local_asset_manifest_from_project
        from figma_flutter_agent.schemas import merge_asset_manifests
        from figma_flutter_agent.stages.assets import (
            export_missing_render_boundary_assets,
            finalize_screen_assets,
        )

        destination_node_ids = {link.destination_node_id for link in ctx.prototype_links}
        exclude_node_ids = build_screen_frame_exclude_ids(parsed.node_id, destination_node_ids)
        raw_manifest = local_asset_manifest_from_project(
            ctx.project_dir,
            exclude_node_ids=exclude_node_ids,
            clean_tree=ctx.clean_tree,
        )
        ctx.asset_manifest, ctx.blocked_asset_paths = finalize_screen_assets(
            project_dir=ctx.project_dir,
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
            ctx.project_dir,
            ctx.asset_manifest,
            strict=settings.agent.assets.strict_render_boundary,
        )
        from figma_flutter_agent.parser.boundaries.assets import (
            resolve_missing_image_asset_keys,
        )

        resolve_missing_image_asset_keys(ctx.clean_tree, ctx.project_dir)
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
                            project_dir=ctx.project_dir,
                            node_ids=frozenset(unresolved),
                            optimize_enabled=settings.agent.assets.optimize,
                        )
                        merge_asset_manifests(raw_manifest, boundary_manifest)
                        ctx.asset_manifest, ctx.blocked_asset_paths = finalize_screen_assets(
                            project_dir=ctx.project_dir,
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

        with log_stage(log, "fonts"):
            ctx.font_manifest = export_fonts(
                FontExportRequest(
                    project_dir=ctx.project_dir,
                    clean_tree=ctx.clean_tree,
                    fonts=settings.agent.fonts,
                    destination_trees=ctx.destination_trees,
                ),
            )
            ctx.warnings.extend(ctx.font_manifest.warnings)


async def run_fetch_parse_live(
    ctx: PipelineContext,
    *,
    parsed: FigmaParsedUrl,
    settings: Settings,
    pipeline_deps: PipelineDependencies,
    log: logger,
    dev_mode_dump: object | None,
    dev_mode_css_override: bool,
    verbose: bool,
    feature_name: str | None,
) -> None:
    """Execute fetch+parse+assets+fonts stages via live Figma API.

    Args:
        ctx: Mutable pipeline context.
        parsed: Parsed Figma URL components.
        settings: Pipeline settings.
        pipeline_deps: Injectable pipeline dependencies.
        log: Bound logger instance.
        dev_mode_dump: Optional Dev Mode CSS dump.
        dev_mode_css_override: Whether Dev Mode CSS overrides style source.
        verbose: Whether verbose mode is active.
        feature_name: Optional explicit feature name.
    """
    from figma_flutter_agent.observability import log_stage
    from figma_flutter_agent.pipeline.helpers import resolve_feature_name
    from figma_flutter_agent.stages import (
        export_figma_assets,
        fetch_figma_frame,
        parse_figma_frame,
    )
    from figma_flutter_agent.stages.assets import AssetExportRequest, finalize_screen_assets
    from figma_flutter_agent.stages.fonts import FontExportRequest, export_fonts
    from figma_flutter_agent.validation.reference import resolve_figma_reference_png

    async with pipeline_deps.figma_connector(
        settings.figma_token(),
        settings.figma_api_base_url,
    ) as connector:
        with log_stage(log, "fetch"):
            fetch_result = await fetch_figma_frame(
                connector,
                file_key=parsed.file_key,
                node_id=parsed.node_id,
                project_dir=ctx.project_dir,
                verbose=verbose,
            )
            ctx.apply_fetch(fetch_result)
        with log_stage(log, "parse"):
            ctx.apply_parse(
                parse_figma_frame(
                    fetch_result,
                    dev_mode_dump=dev_mode_dump,
                    dev_mode_css_override=dev_mode_css_override,
                )
            )
            ctx.enforce_accessibility_gates()
            ctx.apply_accessibility_fixes()

        if not ctx.dry_run and ctx.clean_tree is not None:
            with log_stage(log, "assets"):
                from figma_flutter_agent.parser.boundaries.assets import (
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
                        project_dir=ctx.project_dir,
                        assets=settings.agent.assets,
                        prototype_links=ctx.prototype_links,
                        frame_index=fetch_result.frame_index,
                        primary_node_id=parsed.node_id,
                    ),
                    flatten_exclude_node_ids=flatten_excludes,
                    render_boundary_node_ids=boundary_exports,
                )
                ctx.asset_manifest, ctx.blocked_asset_paths = finalize_screen_assets(
                    project_dir=ctx.project_dir,
                    clean_tree=ctx.clean_tree,
                    destination_trees=ctx.destination_trees,
                    manifest=exported_manifest,
                    primary_node_id=parsed.node_id,
                    destination_node_ids=destination_node_ids,
                )

            with log_stage(log, "fonts"):
                ctx.font_manifest = export_fonts(
                    FontExportRequest(
                        project_dir=ctx.project_dir,
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
                    feature_name or settings.agent.naming.feature_name,
                )
                resolution = await resolve_figma_reference_png(
                    connector=connector,
                    file_key=parsed.file_key,
                    node_id=parsed.node_id,
                    project_dir=ctx.project_dir,
                    feature_name=reference_feature,
                    figma_root=ctx.figma_root,
                    scale=settings.agent.validation.reference_scale,
                    attach_to_llm=attach_to_llm,
                    save_to_disk=save_to_disk,
                    from_dump=False,
                )
                ctx.reference_image_png = resolution.png_bytes
                ctx.reference_image_hash = resolution.image_hash

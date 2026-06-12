"""Wizard Figma fetch/import/dump action handlers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from figma_flutter_agent.figma.url import ParsedFigmaInput

console = Console()


def _wizard_fetch_from_figma(
    ctx: typer.Context, *, parsed: ParsedFigmaInput | None = None
) -> None:
    """Import one frame or dump a full Figma file based on pasted URL."""
    from figma_flutter_agent.dev.project import ensure_project_config
    from figma_flutter_agent.figma.url import FigmaUrlKind
    from figma_flutter_agent.wizard.menus import (
        _file_fetch_menu_options,
        _is_menu_return,
    )
    from figma_flutter_agent.wizard.prompts import (
        prompt_choice,
        prompt_figma_input,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    root = _wizard_project_dir(ctx)
    ensure_project_config(root)
    if parsed is None:
        parsed = prompt_figma_input(ctx=ctx, project_dir=root)

    if parsed.kind == FigmaUrlKind.FRAME:
        _wizard_import_figma_frame(ctx, parsed, project_dir=root)
        return

    mode_label = prompt_choice(
        "File download mode",
        _file_fetch_menu_options(),
        default=_file_fetch_menu_options()[0],
    )
    if _is_menu_return(mode_label):
        return
    advanced = mode_label.startswith("advanced")
    _wizard_dump_figma_file(ctx, parsed, project_dir=root, advanced=advanced)


def _wizard_import_figma_frame(
    ctx: typer.Context,
    parsed: ParsedFigmaInput,
    *,
    project_dir: Path,
) -> None:
    """Import one frame, update the manifest, and optionally preview it."""
    import asyncio

    from figma_flutter_agent.batch.asset_export import FileAssetExportResult, asset_export_gap_hint
    from figma_flutter_agent.batch.dump_mode import (
        BatchDumpMode,
        frame_fetch_mode_from_menu,
    )
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.import_figma import (
        export_figma_frame_assets,
        fetch_figma_frame_display_name,
        import_figma_frame,
    )
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.dev.run import wire_active_screen_blocking
    from figma_flutter_agent.dev.wizard import sync_preview_workflow
    from figma_flutter_agent.figma.client import FigmaConnector
    from figma_flutter_agent.wizard.menus import (
        _default_chrome_device_id,
        _frame_fetch_menu_options,
        _is_menu_return,
        _prompt_import_manifest_mode,
        _wizard_pick_flutter_device,
    )
    from figma_flutter_agent.wizard.prompts import (
        print_pipeline_warnings,
        prompt_choice,
        prompt_confirm,
        prompt_import_feature_name,
    )
    from figma_flutter_agent.wizard.state import (
        _persist_active_screen,
    )

    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)

    from figma_flutter_agent.batch.manifest import BatchManifest, load_batch_manifest

    scope_label = prompt_choice(
        "Frame download scope",
        _frame_fetch_menu_options(),
        default=_frame_fetch_menu_options()[0],
    )
    if _is_menu_return(scope_label):
        return
    fetch_mode = frame_fetch_mode_from_menu(scope_label)
    manifest_path = resolve_manifest_path(project_dir)

    if fetch_mode is BatchDumpMode.MEDIA:
        async def _run_assets() -> tuple[str, FileAssetExportResult]:
            async with FigmaConnector(token, settings.figma_api_base_url) as connector:
                return await export_figma_frame_assets(
                    connector,
                    parsed,
                    manifest_path=manifest_path,
                )

        try:
            feature, asset_result = asyncio.run(_run_assets())
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            return
        console.print(
            f"[green]Assets exported[/green] {feature} ({parsed.node_id}): "
            f"{asset_result.icon_count} SVG, {asset_result.raster_count} raster"
        )
        import json

        from figma_flutter_agent.batch.asset_export import resolve_screen_dump_path

        manifest = load_batch_manifest(manifest_path)
        screen = next(item for item in manifest.screens if item.feature == feature)
        dump_path = resolve_screen_dump_path(screen, manifest.project_dir)
        document = json.loads(dump_path.read_text(encoding="utf-8"))
        gap_hint = asset_export_gap_hint(document, settings.agent.assets, asset_result)
        if gap_hint:
            console.print(f"[yellow]{gap_hint}[/yellow]")
        _persist_active_screen(ctx, feature)
        return

    merge = _prompt_import_manifest_mode(manifest_path)

    async def _run_import() -> tuple[str, Path, FileAssetExportResult | None]:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            frame_name = await fetch_figma_frame_display_name(connector, parsed)
            if manifest_path.is_file():
                manifest = load_batch_manifest(manifest_path)
            else:
                manifest = BatchManifest(
                    file_key=parsed.file_key,
                    project_dir=project_dir,
                    screens=(),
                )
            chosen_slug = prompt_import_feature_name(
                frame_name,
                manifest,
                parsed.node_id,
            )
            return await import_figma_frame(
                connector,
                parsed,
                project_dir=project_dir,
                manifest_path=manifest_path,
                merge=merge,
                feature_name=chosen_slug,
                mode=fetch_mode,
            )

    feature, dump_path, asset_result = asyncio.run(_run_import())
    asset_line = ""
    if asset_result is not None:
        asset_line = f", {asset_result.icon_count} SVG, {asset_result.raster_count} raster"
    scope_note = " (JSON only)" if fetch_mode is BatchDumpMode.JSON else ""
    console.print(
        f"[green]Imported frame[/green] {feature} ({parsed.node_id}) → "
        f"{dump_path.as_posix()}{asset_line}{scope_note}"
    )
    if asset_result is not None:
        import json

        document = json.loads(dump_path.read_text(encoding="utf-8"))
        gap_hint = asset_export_gap_hint(document, settings.agent.assets, asset_result)
        if gap_hint:
            console.print(f"[yellow]{gap_hint}[/yellow]")
    _persist_active_screen(ctx, feature)
    if prompt_confirm("Generate and preview this screen now (live sync)?", default=True):
        device_id = _default_chrome_device_id(
            flutter_sdk=load_settings().flutter_sdk or None,
        )
        if device_id is None:
            device_id = _wizard_pick_flutter_device()
        _, launched, pipeline_result = asyncio.run(
            sync_preview_workflow(
                project_dir=project_dir,
                screen_name=feature,
                prefer_live=True,
                device_id=device_id,
            )
        )
        print_pipeline_warnings(pipeline_result.warnings)
        if launched is False:
            console.print(f"[yellow]Sync complete — Flutter run stopped.[/yellow] — {feature}")
        else:
            console.print(f"[green]Sync & preview complete[/green] — {feature}")
    elif prompt_confirm("Wire main.dart to this screen?", default=True):
        wire_active_screen_blocking(
            project_dir=project_dir, screen_name=feature, allow_dev_profile=True
        )
        console.print(f"[green]Active screen wired:[/green] {feature}")


def _wizard_dump_figma_file(
    ctx: typer.Context,
    parsed: ParsedFigmaInput,
    *,
    project_dir: Path,
    advanced: bool,
) -> None:
    """Dump a full Figma file with quick defaults or advanced scope/policy."""
    import asyncio

    from figma_flutter_agent.batch.dump_mode import (
        BatchDumpMode,
        DumpWritePolicy,
        assets_attempted,
        batch_dump_menu_options,
        batch_dump_mode_from_menu,
        default_write_policy,
        plan_for_mode,
        write_policy_from_menu,
        write_policy_menu_options,
    )
    from figma_flutter_agent.batch.file_dump import dump_full_figma_file
    from figma_flutter_agent.batch.screen_report import (
        print_screen_download_report,
        screen_download_all_ok,
    )
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.figma.client import FigmaConnector
    from figma_flutter_agent.wizard.menus import _prompt_import_manifest_mode
    from figma_flutter_agent.wizard.prompts import prompt_choice

    if advanced:
        mode_label = prompt_choice(
            "Batch download scope",
            batch_dump_menu_options(),
            default=batch_dump_menu_options()[0],
        )
        dump_mode = batch_dump_mode_from_menu(mode_label)
        dump_plan = plan_for_mode(dump_mode)
        if dump_plan.write_json or assets_attempted(dump_plan):
            policy_label = prompt_choice(
                "Write policy",
                write_policy_menu_options(),
                default=(
                    write_policy_menu_options()[0]
                    if default_write_policy(dump_mode) is DumpWritePolicy.SKIP_EXISTING
                    else write_policy_menu_options()[1]
                ),
            )
            write_policy = write_policy_from_menu(policy_label)
        else:
            write_policy = DumpWritePolicy.REWRITE
    else:
        dump_mode = BatchDumpMode.ALL
        write_policy = DumpWritePolicy.REWRITE
        dump_plan = plan_for_mode(dump_mode)

    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)

    manifest_path = resolve_manifest_path(project_dir)
    manifest_merge = _prompt_import_manifest_mode(manifest_path)

    async def _run() -> object:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            return await dump_full_figma_file(
                connector,
                file_key=parsed.file_key,
                project_dir=project_dir,
                manifest_path=manifest_path,
                mode=dump_mode,
                write_policy=write_policy,
                assets=settings.agent.assets,
                manifest_merge=manifest_merge,
            )

    result = asyncio.run(_run())
    assets_exported = assets_attempted(dump_plan)
    console.print(
        f"[green]Fetched file[/green] mode={dump_mode.value}, {len(result.screens)} screens, "
        f"{result.icon_count} SVG, {result.raster_count} raster"
    )
    print_screen_download_report(
        console,
        result.screen_reports,
        with_assets=assets_exported,
        orphan_exportables=result.orphan_exportables,
        rate_limited=result.rate_limited,
    )
    if not screen_download_all_ok(result.screen_reports, with_assets=assets_exported):
        raise typer.Exit(code=1)
    console.print(
        "[dim]Slugs were derived from Figma layer names. "
        "Use list → rename to adjust feature names.[/dim]"
    )

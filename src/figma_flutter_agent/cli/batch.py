"""Batch dump and offline generate commands."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from figma_flutter_agent.batch.dump_mode import (
    BatchDumpMode,
    DumpWritePolicy,
    assets_attempted,
    plan_for_mode,
)
from figma_flutter_agent.config import apply_production_profile, load_settings
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.logging_setup import configure_logging
from figma_flutter_agent.wizard import is_interactive, prompt_manifest_path

from .helpers import (
    _handle_cli_exception,
    _resolve_flutter_project,
    console,
)

app = typer.Typer(help="Batch dump and offline generate for many screens.")


@app.command("dump")
def batch_dump_command(
    ctx: typer.Context,
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Path to screens.yaml batch manifest",
    ),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--no-skip-existing",
        help="Skip screens that already have a dump file",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
) -> None:
    """Fetch one Figma node per screen and write raw layout dumps (1 Tier-1 call each)."""
    from figma_flutter_agent.batch.dump import dump_manifest_screens
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.figma.client import FigmaConnector

    configure_logging(verbose=verbose)
    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)

    if manifest is None:
        if is_interactive(ctx):
            root = _resolve_flutter_project(ctx, Path("."))
            manifest = prompt_manifest_path(ctx, root)
        else:
            console.print("[red]--manifest is required[/red]")
            raise typer.Exit(code=1)

    try:
        batch_manifest = load_batch_manifest(manifest.resolve())
    except ValueError as exc:
        console.print(f"[red]Invalid manifest:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    async def _run() -> None:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            written = await dump_manifest_screens(
                connector,
                batch_manifest,
                skip_existing=skip_existing,
            )
        console.print(f"[green]Batch dump complete[/green] ({len(written)} screens)")
        for screen, path in written:
            console.print(f"  - {screen.feature}: {path.as_posix()}")

    try:
        asyncio.run(_run())
    except BaseException as exc:
        _handle_cli_exception(exc, command="batch dump", verbose=verbose)


@app.command("dump-file")
def batch_dump_file_command(
    ctx: typer.Context,
    project_dir: Path = typer.Option(
        Path("."),
        "--project-dir",
        help="Target Flutter project root",
    ),
    figma_url: str | None = typer.Option(
        None,
        "--figma-url",
        help="Figma file URL (with or without node-id)",
    ),
    file_key: str | None = typer.Option(
        None, "--file-key", help="Figma file key (alternative to URL)"
    ),
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Write screens.yaml here (default: <project-dir>/screens.yaml)",
    ),
    skip_existing_screens: bool | None = typer.Option(
        None,
        "--skip-existing-screens/--rewrite-screens",
        help="Keep existing .figma_debug/raw/*_layout.json; default follows --write-policy",
    ),
    write_policy: DumpWritePolicy | None = typer.Option(
        None,
        "--write-policy",
        help="rewrite or skip-existing — skip uses local files, no extra Figma API",
        case_sensitive=False,
    ),
    mode: BatchDumpMode | None = typer.Option(
        None,
        "--mode",
        help="Dump scope: all, json, media, vector, raster (media modes use cached JSON)",
        case_sensitive=False,
    ),
    with_assets: bool | None = typer.Option(
        None,
        "--with-assets/--json-only",
        help="Legacy shorthand: --json-only equals --mode json; default is --mode all",
    ),
    no_write_manifest: bool = typer.Option(
        False,
        "--no-write-manifest",
        help="Do not write or overwrite screens.yaml",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
) -> None:
    """Fetch entire Figma file: JSON tree, screen dumps, manifest, and all SVG/PNG assets."""
    from figma_flutter_agent.batch.dump_mode import default_write_policy, resolve_batch_dump_mode
    from figma_flutter_agent.batch.file_dump import dump_full_figma_file
    from figma_flutter_agent.batch.screen_report import (
        print_screen_download_report,
        screen_download_all_ok,
    )
    from figma_flutter_agent.errors import FigmaUrlError
    from figma_flutter_agent.figma.client import FigmaConnector
    from figma_flutter_agent.figma.url import parse_figma_file_key

    configure_logging(verbose=verbose)
    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)

    resolved_key = file_key.strip() if file_key else None
    if figma_url and figma_url.strip():
        try:
            resolved_key = parse_figma_file_key(figma_url.strip())
        except FigmaUrlError as exc:
            console.print(f"[red]Invalid --figma-url:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    if not resolved_key:
        if is_interactive(ctx):
            from figma_flutter_agent.wizard import prompt_figma_file_key

            resolved_key = prompt_figma_file_key()
        else:
            console.print("[red]Provide --figma-url or --file-key[/red]")
            raise typer.Exit(code=1)

    try:
        project_root = _resolve_flutter_project(ctx, project_dir)
    except FlutterProjectError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    manifest_path = manifest.resolve() if manifest is not None else None
    resolved_mode = resolve_batch_dump_mode(mode=mode, with_assets=with_assets)
    resolved_write_policy = write_policy or default_write_policy(resolved_mode)

    async def _run() -> None:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            return await dump_full_figma_file(
                connector,
                file_key=resolved_key,
                project_dir=project_root,
                manifest_path=manifest_path,
                write_manifest=not no_write_manifest,
                mode=resolved_mode,
                write_policy=resolved_write_policy,
                skip_existing_screens=skip_existing_screens,
                assets=settings.agent.assets,
            )

    try:
        result = asyncio.run(_run())
    except BaseException as exc:
        _handle_cli_exception(exc, command="batch dump-file", verbose=verbose)

    title = result.file_name or result.file_key
    dump_plan = plan_for_mode(result.mode)
    assets_exported = assets_attempted(dump_plan)
    all_ok = screen_download_all_ok(result.screen_reports, with_assets=assets_exported)
    headline = (
        "[green]Full file dump OK[/green]" if all_ok else "[yellow]Full file dump partial[/yellow]"
    )
    console.print(
        f"{headline} {title!r} — mode={result.mode.value}, "
        f"write={resolved_write_policy.value}, {len(result.screens)} screen(s)"
    )
    console.print(f"  full: {result.full_file_path.as_posix()}")
    if assets_exported:
        asset_bits: list[str] = []
        if dump_plan.export_svg:
            asset_bits.append("SVG")
        if dump_plan.export_raster or dump_plan.export_blur_png:
            asset_bits.append("raster")
        console.print(
            f"  assets ({'+'.join(asset_bits)}): "
            f"{result.icon_count} SVG icon(s), {result.raster_count} raster file(s)"
        )
    else:
        console.print("  assets: skipped (json-only mode)")
    if result.manifest_path is not None:
        console.print(f"  manifest: {result.manifest_path.as_posix()}")
    print_screen_download_report(
        console,
        result.screen_reports,
        with_assets=assets_exported,
        orphan_exportables=result.orphan_exportables,
        rate_limited=result.rate_limited,
    )
    if not all_ok:
        raise typer.Exit(code=1)


@app.command("generate")
def batch_generate_command(
    ctx: typer.Context,
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Path to screens.yaml batch manifest",
    ),
    config: Path | None = typer.Option(
        None, "--config", help="Path to agent .ai-figma-flutter.yml (default: repo root)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan without writing files"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
    regenerate_templates: bool = typer.Option(
        False,
        "--regenerate-templates",
        help="Force rewrite of all planned files during incremental sync",
    ),
    allow_dev_profile: bool = typer.Option(
        False,
        "--allow-dev-profile",
        help="Skip production gates (not suitable for release sign-off)",
    ),
    require_dump: bool = typer.Option(
        True,
        "--require-dump/--allow-live",
        help="Require cached dumps (default) or call live Figma API per screen",
    ),
) -> None:
    """Generate Flutter outputs for every screen in the manifest (offline when dumps exist)."""
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import run_batch_generate

    configure_logging(verbose=verbose)
    if manifest is None:
        if is_interactive(ctx):
            root = _resolve_flutter_project(ctx, Path("."))
            manifest = prompt_manifest_path(ctx, root)
        else:
            console.print("[red]--manifest is required[/red]")
            raise typer.Exit(code=1)

    try:
        batch_manifest = load_batch_manifest(manifest.resolve())
    except ValueError as exc:
        console.print(f"[red]Invalid manifest:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if config is None:
        from figma_flutter_agent.dev.project import ensure_project_config

        config = ensure_project_config(batch_manifest.project_dir)
    settings = load_settings(config)
    if not dry_run and not allow_dev_profile:
        settings = apply_production_profile(settings)
    elif not dry_run and allow_dev_profile:
        console.print(
            "[yellow]Dev profile:[/yellow] production gates disabled (--allow-dev-profile)."
        )

    batch_force_llm_regen = True

    try:
        report = asyncio.run(
            run_batch_generate(
                batch_manifest,
                settings,
                dry_run=dry_run,
                verbose=verbose,
                allow_dev_profile=allow_dev_profile,
                regenerate_templates=regenerate_templates,
                require_dump=require_dump,
                force_llm_regen=batch_force_llm_regen,
            )
        )
    except BaseException as exc:
        _handle_cli_exception(exc, command="batch generate", verbose=verbose)

    for item in report.results:
        if item.success:
            files = (
                item.pipeline.written_files or item.pipeline.planned_files if item.pipeline else []
            )
            console.print(f"[green]OK[/green] {item.feature} ({len(files)} files)")
        else:
            console.print(f"[red]FAIL[/red] {item.feature}: {item.error}")

    if report.passed:
        console.print(f"[green]Batch generate complete[/green] ({len(report.results)} screens)")
        raise typer.Exit(code=0)

    console.print(
        f"[red]Batch generate failed[/red] ({len(report.failures)} of {len(report.results)})"
    )
    raise typer.Exit(code=1)

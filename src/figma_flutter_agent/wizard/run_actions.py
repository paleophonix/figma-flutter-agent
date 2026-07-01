"""Wizard run/preview action handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from figma_flutter_agent.config import Settings

console = Console()


def report_plan_failure_stale_preview() -> None:
    """Warn that Chrome preview still reflects the previous successful writeback."""
    console.print("[bold red]Codegen failed before writeback — Chrome preview is stale.[/bold red]")
    console.print("[dim]plan: failed | writeback: skipped | served_preview: previous build[/dim]")


def report_launch_preflight_failure() -> None:
    """Warn when generate succeeded but Flutter launch was blocked by pre-flight gates."""
    console.print(
        "[bold red]Launch blocked by pre-flight graph gate — Chrome preview is stale.[/bold red]"
    )
    console.print(
        "[dim]plan: ok | writeback: ok | launch: blocked | served_preview: previous build[/dim]"
    )


def report_preview_launch_failure() -> None:
    """Warn when codegen/writeback succeeded but ``flutter run`` preview launch failed."""
    console.print(
        "[bold yellow]Codegen complete — preview launch failed (Flutter run did not start).[/bold yellow]"
    )
    console.print(
        "[dim]plan: ok | writeback: committed | launch: failed | served_preview: previous build[/dim]"
    )


def _wizard_run(ctx: typer.Context) -> None:
    """Launch Flutter after optional generate/asset-sync submenu selection."""
    from figma_flutter_agent.dev.project import ensure_project_config
    from figma_flutter_agent.wizard.capture_prompt import prompt_wizard_capture_settings
    from figma_flutter_agent.wizard.menus import _is_menu_return, _run_menu_options
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    mode_label = prompt_choice(
        "Run pipeline",
        _run_menu_options(),
        default=_run_menu_options()[0],
    )
    if _is_menu_return(mode_label):
        return
    command = _menu_command(mode_label)
    root = _wizard_project_dir(ctx)
    config_path = ensure_project_config(root)
    settings = prompt_wizard_capture_settings(config_path)
    capture_note = "on" if settings.agent.dev.debug_capture else "off"
    console.print(f"[dim]Golden capture:[/dim] {capture_note}")
    if command == "ir-offline":
        _wizard_sync_preview(ctx, prefer_live=False, use_cached_ir=True, settings=settings)
        return
    prefer_live = command != "offline"
    _wizard_sync_preview(ctx, prefer_live=prefer_live, settings=settings)


def _wizard_launch_defaults(ctx: typer.Context) -> None:
    """Run cached dump + screen IR codegen, then ``flutter run`` on Chrome without prompts."""
    _wizard_sync_preview(
        ctx,
        prefer_live=False,
        use_default_launch=True,
        use_cached_ir=True,
    )


def _wizard_sync_preview(
    ctx: typer.Context,
    *,
    prefer_live: bool | None = False,
    use_default_launch: bool = False,
    use_cached_ir: bool = False,
    settings: Settings | None = None,
) -> None:
    """Sync one screen from Figma (live when needed) and launch Flutter."""
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.config import (
        apply_interactive_preview_profile,
        load_settings,
    )
    from figma_flutter_agent.dev.project import (
        ensure_project_config,
        resolve_manifest_path,
    )
    from figma_flutter_agent.dev.wizard import (
        build_run_plan,
        collect_screen_preflight,
        format_screen_preflight,
        resolve_flutter_device_id_from_settings,
        sync_preview_workflow,
    )
    from figma_flutter_agent.wizard.menus import (
        _resolve_run_prefer_live,
    )
    from figma_flutter_agent.wizard.prompts import (
        ensure_llm_generation_ready,
        print_pipeline_warnings,
    )
    from figma_flutter_agent.wizard.screens import _wizard_resolve_screen
    from figma_flutter_agent.wizard.state import (
        _persist_active_screen,
        _wizard_project_dir,
    )

    root = _wizard_project_dir(ctx)
    ensure_project_config(root)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    screen = _wizard_resolve_screen(ctx, manifest, without_prompts=use_default_launch)
    _persist_active_screen(ctx, screen)

    plan = build_run_plan(project_dir=root, screen_name=screen)
    preflight = collect_screen_preflight(plan)

    settings = settings if settings is not None else load_settings(plan.config_path)
    if use_default_launch:
        settings = apply_interactive_preview_profile(settings)
    has_token = bool(settings.figma_token().strip())

    if use_cached_ir:
        from figma_flutter_agent.debug.ir_load import resolve_screen_ir_dump_path
        from figma_flutter_agent.debug.paths import debug_path_display
        from figma_flutter_agent.errors import FlutterProjectError

        prefer_live = False
        if not plan.dump_path.is_file():
            raise FileNotFoundError(
                f"Dump missing for {screen}: {plan.dump_path.as_posix()}. "
                "Run batch dump-file or fetch first."
            )
        try:
            ir_path = resolve_screen_ir_dump_path(plan.project_dir, screen)
        except FlutterProjectError as exc:
            raise FlutterProjectError(
                f"No cached screen IR for {screen!r}. Run generate with use_screen_ir "
                f"or place JSON under .debug/ir/. {exc}"
            ) from exc
        console.print(f"[dim]Screen IR:[/dim] {debug_path_display(ir_path, plan.project_dir)}")
    else:
        prefer_live = _resolve_run_prefer_live(
            prefer_live=prefer_live,
            has_token=has_token,
        )
    full_selected = prefer_live is True

    if use_cached_ir:
        console.print(
            "[dim]Run mode:[/dim] ir-offline — cached dump + screen IR, no LLM/Figma fetch"
        )
    elif prefer_live is False:
        console.print("[dim]Run mode:[/dim] offline — cached dump, no live asset sync")
    elif prefer_live is True:
        console.print("[dim]Run mode:[/dim] full — sync from live Figma")
    elif not preflight.needs_live_sync:
        console.print("[dim]Run mode:[/dim] launch — cached dump (no live frame fetch)")
    elif preflight.dump_exists and not has_token:
        console.print("[dim]Run mode:[/dim] no FIGMA token — using cached dump")
    elif preflight.dump_exists and has_token and preflight.missing_asset_exports > 0:
        console.print(
            "[dim]Run mode:[/dim] cached dump — "
            f"{preflight.missing_asset_exports} asset(s) missing on disk; "
            "use run → full or batch dump-file (media) to backfill"
        )
    elif preflight.dump_exists:
        console.print("[dim]Run mode:[/dim] cached dump")
    elif preflight.needs_live_sync:
        console.print(
            "[yellow]No FIGMA token and dump/assets missing — live sync unavailable.[/yellow]"
        )

    console.print(
        format_screen_preflight(
            preflight,
            prefer_live=prefer_live is True,
            prefer_offline=prefer_live is False,
            full_selected=full_selected and prefer_live is not True,
        )
    )

    if use_cached_ir:
        force_llm_regen = False
        console.print("[dim]Codegen:[/dim] IR emit from .debug/ir (LLM skipped)")
    elif use_default_launch:
        console.print(f"[dim]Screen:[/dim] {screen}")
        ensure_llm_generation_ready(settings)
        force_llm_regen = True
        console.print("[dim]Codegen:[/dim] LLM screen IR + emitter")
    else:
        ensure_llm_generation_ready(settings)
        force_llm_regen = True
        console.print("[dim]Codegen:[/dim] LLM screen IR + emitter")

    device_id = resolve_flutter_device_id_from_settings(settings)
    device_label = device_id or "default device"
    preview_mode = settings.agent.responsive.mode
    if use_default_launch and not use_cached_ir:
        console.print(f"[dim]Screen:[/dim] {screen}")
    console.print(f"[dim]Device:[/dim] {device_label} ({preview_mode} Chrome preview)")
    console.print(f"[dim]Launching Flutter on {device_label} after sync…[/dim]")
    console.print("[dim]Pipeline:[/dim] starting sync (preflight cached when possible)…")
    try:
        _, launched, pipeline_result = asyncio.run(
            sync_preview_workflow(
                project_dir=root,
                screen_name=screen,
                prefer_live=prefer_live,
                device_id=device_id,
                settings=settings,
                force_llm_regen=force_llm_regen,
                use_cached_ir=use_cached_ir,
                preflight=preflight,
            )
        )
    except Exception as exc:
        if "pre_launch_stale_import_scan" in str(exc):
            report_launch_preflight_failure()
        else:
            report_plan_failure_stale_preview()
        raise
    from figma_flutter_agent.fonts.diagnostics import format_wizard_font_report

    fonts_ok, font_lines = format_wizard_font_report(
        root,
        dump_path=plan.dump_path,
        screen=screen,
        scope="full",
    )
    if not fonts_ok:
        console.print("[bold yellow]Fonts before launch[/bold yellow]")
        for line in font_lines:
            console.print(line)
        console.print()
    print_pipeline_warnings(pipeline_result.warnings)
    if launched is None:
        report_preview_launch_failure()
        console.print(
            f"[yellow]Codegen complete — preview launch failed.[/yellow] — {screen}"
        )
    elif launched is False:
        console.print(f"[yellow]Sync complete — Flutter run stopped.[/yellow] — {screen}")
    else:
        console.print(f"[green]Run complete[/green] — {screen}")

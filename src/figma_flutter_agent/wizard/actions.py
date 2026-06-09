"""Wizard action handlers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from figma_flutter_agent.batch.manifest import BatchManifest
    from figma_flutter_agent.figma.url import ParsedFigmaInput

console = Console()


def _wizard_resolve_screen(
    ctx: typer.Context,
    manifest: BatchManifest,
    *,
    without_prompts: bool = False,
) -> str:
    """Return active screen or prompt to pick one.

    Args:
        ctx: Wizard session context.
        manifest: Batch manifest for the current Flutter project.
        without_prompts: When True (``launch`` defaults), use active or sole screen
            without confirmation menus.

    Returns:
        Feature slug for the screen to run.
    """
    from figma_flutter_agent.wizard.prompts import prompt_confirm
    from figma_flutter_agent.wizard.state import _wizard_active_screen_label

    options = [screen.feature for screen in manifest.screens]
    if not options:
        msg = "No screens in screens.yaml"
        raise ValueError(msg)

    active = _wizard_active_screen_label(ctx)
    option_set = set(options)

    if without_prompts:
        if active is not None and active in option_set:
            return active
        if len(options) == 1:
            return options[0]
        if active is not None and active not in option_set:
            console.print(
                f"[yellow]Active screen '{active}' not in manifest; using '{options[0]}'.[/yellow]"
            )
            return options[0]
        return options[0]

    if (
        active is not None
        and active in option_set
        and prompt_confirm(f"Use active screen '{active}'?", default=True)
    ):
        return active
    return _wizard_pick_screen(ctx, manifest)


def _wizard_resolve_active_dump(ctx: typer.Context) -> Path | None:
    """Return the dump path for the wizard active screen, if known."""
    from figma_flutter_agent.batch.manifest import find_screen_entry, load_batch_manifest
    from figma_flutter_agent.batch.run import _resolve_dump
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.wizard.state import (
        _wizard_active_screen_label,
        _wizard_project_dir,
    )

    root = _wizard_project_dir(ctx)
    manifest_path = resolve_manifest_path(root)
    if not manifest_path.is_file():
        return None
    screen = _wizard_active_screen_label(ctx)
    if not screen:
        return None
    manifest = load_batch_manifest(manifest_path)
    entry = find_screen_entry(manifest, screen)
    dump_path = _resolve_dump(entry, manifest.project_dir)
    return dump_path if dump_path.is_file() else None


def _wizard_print_font_audit(ctx: typer.Context) -> bool:
    """Print font diagnostics for the current Flutter project. Returns False when any row fails."""
    from figma_flutter_agent.fonts.diagnostics import format_wizard_font_report
    from figma_flutter_agent.wizard.state import (
        _wizard_active_screen_label,
        _wizard_project_dir,
    )

    root = _wizard_project_dir(ctx)
    dump_path = _wizard_resolve_active_dump(ctx)
    screen = _wizard_active_screen_label(ctx)
    console.print("[bold]Fonts[/bold]")
    passed, lines = format_wizard_font_report(
        root,
        dump_path=dump_path,
        screen=screen,
    )
    for line in lines:
        console.print(line)
    console.print()
    return passed


def _wizard_check(ctx: typer.Context) -> None:
    """Run doctor, live-check, or both based on submenu selection."""
    from figma_flutter_agent.wizard.menus import _check_menu_options
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice

    mode_label = prompt_choice(
        "Check mode",
        _check_menu_options(),
        default=_check_menu_options()[0],
    )
    mode = _menu_command(mode_label)
    failed = False
    if mode in {"all", "fonts"}:
        if not _wizard_print_font_audit(ctx):
            failed = True
        if mode == "fonts":
            if failed:
                raise typer.Exit(code=1)
            return
    if mode in {"all", "doctor"}:
        try:
            _wizard_doctor(ctx)
        except typer.Exit as exc:
            if exc.exit_code:
                failed = True
            else:
                raise
    if mode in {"all", "live-check"}:
        try:
            _wizard_live_check(ctx)
        except typer.Exit as exc:
            if exc.exit_code:
                failed = True
            else:
                raise
    if failed:
        raise typer.Exit(code=1)


def _wizard_generate_menu(ctx: typer.Context) -> None:
    """Run batch or single-screen codegen based on submenu selection."""
    from figma_flutter_agent.wizard.menus import _generate_menu_options
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice

    mode_label = prompt_choice(
        "Generate mode",
        _generate_menu_options(),
        default=_generate_menu_options()[0],
    )
    if _menu_command(mode_label) == "batch":
        _wizard_batch_generate(ctx)
    else:
        _wizard_generate(ctx)


def _wizard_run(ctx: typer.Context) -> None:
    """Launch Flutter after optional generate/asset-sync submenu selection."""
    from figma_flutter_agent.wizard.menus import _run_menu_options
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice

    mode_label = prompt_choice(
        "Run pipeline",
        _run_menu_options(),
        default=_run_menu_options()[0],
    )
    command = _menu_command(mode_label)
    if command == "ir-offline":
        _wizard_sync_preview(ctx, prefer_live=False, use_cached_ir=True)
        return
    prefer_live = command != "offline"
    _wizard_sync_preview(ctx, prefer_live=prefer_live)


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
        sync_preview_workflow,
    )
    from figma_flutter_agent.wizard.menus import (
        _default_chrome_device_id,
        _resolve_run_prefer_live,
        _wizard_pick_flutter_device,
    )
    from figma_flutter_agent.wizard.prompts import (
        ensure_llm_generation_ready,
        print_pipeline_warnings,
    )
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

    settings = load_settings(plan.config_path)
    if use_default_launch:
        settings = apply_interactive_preview_profile(settings)
    has_token = bool(settings.figma_token().strip())

    if use_cached_ir:
        from figma_flutter_agent.debug.ir_load import resolve_screen_ir_dump_path
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
                f"or place JSON under .figma_debug/ir/. {exc}"
            ) from exc
        console.print(
            f"[dim]Screen IR:[/dim] {ir_path.relative_to(plan.project_dir).as_posix()}"
        )
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
        console.print("[dim]Codegen:[/dim] IR emit from .figma_debug/ir (LLM skipped)")
    elif use_default_launch:
        console.print(f"[dim]Screen:[/dim] {screen}")
        ensure_llm_generation_ready(settings)
        force_llm_regen = True
        console.print("[dim]Codegen:[/dim] LLM screen IR + emitter")
    else:
        ensure_llm_generation_ready(settings)
        force_llm_regen = True
        console.print("[dim]Codegen:[/dim] LLM screen IR + emitter")

    device_id = _default_chrome_device_id(flutter_sdk=settings.flutter_sdk or None)
    if device_id is None:
        device_id = _wizard_pick_flutter_device(flutter_sdk=settings.flutter_sdk or None)
    device_label = device_id or "default device"
    if use_default_launch and not use_cached_ir:
        console.print(f"[dim]Screen:[/dim] {screen}")
    console.print(f"[dim]Device:[/dim] {device_label} (artboard-sized Chrome preview)")
    console.print(f"[dim]Launching Flutter on {device_label} after sync…[/dim]")
    _, launched, pipeline_result = asyncio.run(
        sync_preview_workflow(
            project_dir=root,
            screen_name=screen,
            prefer_live=prefer_live,
            device_id=device_id,
            settings=settings,
            force_llm_regen=force_llm_regen,
            use_cached_ir=use_cached_ir,
        )
    )
    from figma_flutter_agent.fonts.diagnostics import format_wizard_font_report

    fonts_ok, font_lines = format_wizard_font_report(
        root,
        dump_path=plan.dump_path,
        screen=screen,
    )
    if not fonts_ok:
        console.print("[bold yellow]Fonts before launch[/bold yellow]")
        for line in font_lines:
            console.print(line)
        console.print()
    print_pipeline_warnings(pipeline_result.warnings)
    if launched is False:
        console.print(f"[yellow]Sync complete — Flutter run stopped.[/yellow] — {screen}")
    else:
        console.print(f"[green]Run complete[/green] — {screen}")


def _wizard_doctor(ctx: typer.Context) -> None:
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.wizard import (
        collect_doctor_report,
        format_doctor_report,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    root = _wizard_project_dir(ctx)
    settings = load_settings()
    report = collect_doctor_report(project_dir=root, settings=settings)
    console.print(format_doctor_report(report))
    if not report.passed:
        raise typer.Exit(code=1)


def _wizard_flutter_analyze(ctx: typer.Context) -> None:
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.wizard import run_flutter_analyze
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    root = _wizard_project_dir(ctx)
    settings = load_settings()
    run_flutter_analyze(root, flutter_sdk=settings.flutter_sdk or None)
    console.print("[green]flutter analyze passed[/green]")


def _wizard_debug_view(ctx: typer.Context) -> None:
    """Preview a cached bundle and/or write combat renders under ``logs/renders/``."""
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.config import apply_interactive_preview_profile, load_settings
    from figma_flutter_agent.dev.debug_view import launch_debug_view
    from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
    from figma_flutter_agent.dev.view_renders import run_view_combat_renders
    from figma_flutter_agent.wizard.menus import (
        _default_chrome_device_id,
        _prompt_view_bundle_choice,
        _view_menu_options,
        _wizard_pick_flutter_device,
    )
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice
    from figma_flutter_agent.wizard.state import (
        _persist_active_screen,
        _wizard_project_dir,
    )

    root = _wizard_project_dir(ctx)
    ensure_project_config(root)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    screen = _wizard_resolve_screen(ctx, manifest)
    _persist_active_screen(ctx, screen)

    mode_label = prompt_choice(
        "View mode",
        _view_menu_options(),
        default=_view_menu_options()[0],
    )
    mode = _menu_command(mode_label)

    bundle_choice = _prompt_view_bundle_choice(root, screen)
    console.print(f"[dim]Bundle:[/dim] {bundle_choice.path.as_posix()}")
    settings = apply_interactive_preview_profile(load_settings(ensure_project_config(root)))

    if mode in {"renders", "full"}:
        console.print("[dim]Capturing combat renders (Figma ref, Flutter golden, diff)…[/dim]")
        console.print(
            "[dim]Flutter capture uses `flutter test` (VM test compile), not `flutter run` "
            "(Chrome web). That is a separate, heavier compile — Chrome preview can start in "
            "seconds while the first capture still needs several minutes. Docker is for CI "
            "reproducibility, not faster local wizard capture. Capture timeout is 20 min "
            "(kill the terminal if it hangs). "
            "Compiler lines stream below.[/dim]"
        )
        try:
            render_result = asyncio.run(
                run_view_combat_renders(
                    root,
                    feature_name=screen,
                    bundle_path=bundle_choice.path,
                    settings=settings,
                )
            )
        except Exception as exc:
            console.print(f"[red]Combat renders failed:[/red] {exc}")
            if mode == "renders":
                raise typer.Exit(code=1) from exc
            console.print("[yellow]Continuing with preview only.[/yellow]")
        else:
            console.print(
                f"[green]Combat renders saved[/green] → {render_result.render_dir.as_posix()}"
            )
            if render_result.changed_ratio is not None:
                console.print(
                    f"[dim]Pixel diff:[/dim] {render_result.changed_ratio:.2%} changed vs Figma"
                )
            for warning in render_result.warnings:
                console.print(f"[yellow]{warning}[/yellow]")
            if not render_result.flutter_capture_ok and mode == "renders":
                raise typer.Exit(code=1)

    if mode not in {"preview", "full"}:
        return

    device_id = _default_chrome_device_id(flutter_sdk=settings.flutter_sdk or None)
    if device_id is None:
        device_id = _wizard_pick_flutter_device(flutter_sdk=settings.flutter_sdk or None)
    launched = launch_debug_view(
        root,
        feature_name=screen,
        bundle_path=bundle_choice.path,
        device_id=device_id,
        settings=settings,
    )
    if launched is False:
        console.print(f"[yellow]Preview stopped[/yellow] — {screen}")
    else:
        console.print(f"[green]Preview launched[/green] — {screen}")


def _wizard_agent_signoff(ctx: typer.Context) -> None:
    from figma_flutter_agent.dev.wizard import agent_repo_root, run_agent_signoff
    from figma_flutter_agent.wizard.prompts import prompt_confirm

    if not prompt_confirm(
        "Run offline test gates (demo-signoff + pytest)? This may take several minutes.",
        default=False,
    ):
        console.print("[yellow]Skipped.[/yellow]")
        return
    run_agent_signoff(agent_root=agent_repo_root())
    console.print("[green]Test gates passed[/green]")


def _wizard_switch_project(ctx: typer.Context) -> None:
    """Pick the active Flutter app under ``FIGMA_FLUTTER_PROJECT_DIR`` workspace."""
    from figma_flutter_agent.dev.project import (
        discover_flutter_projects,
        env_configured_workspace_root,
        is_flutter_project_root,
    )
    from figma_flutter_agent.errors import FlutterProjectError
    from figma_flutter_agent.wizard.prompts import prompt_choice
    from figma_flutter_agent.wizard.state import (
        _load_persisted_active_screen,
        _persist_active_flutter_project,
        _wizard_state,
        _wizard_workspace_root,
    )

    workspace = _wizard_workspace_root(ctx) or env_configured_workspace_root()
    if workspace is None:
        raise FlutterProjectError(
            "Set FIGMA_FLUTTER_PROJECT_DIR in the agent .env to your Flutter workspace root "
            "(parent folder containing app directories with pubspec.yaml)."
        )
    workspace = workspace.resolve()
    _wizard_state(ctx).workspace_root = workspace

    projects = discover_flutter_projects(workspace)
    if not projects:
        raise FlutterProjectError(
            f"No Flutter projects (pubspec.yaml) found under workspace {workspace.as_posix()}"
        )

    if len(projects) == 1 and is_flutter_project_root(workspace):
        selected = projects[0]
        _persist_active_flutter_project(ctx, selected, workspace_root=workspace)
        console.print(f"[green]Active project:[/green] {selected.as_posix()}")
        return

    state = _wizard_state(ctx)
    labels = [project.name for project in projects]
    default_label = (
        state.project_dir.name
        if state.project_dir is not None and state.project_dir in projects
        else labels[0]
    )
    picked = prompt_choice(
        "Select active Flutter project",
        labels,
        default=default_label,
    )
    selected = next(project for project in projects if project.name == picked)
    _persist_active_flutter_project(ctx, selected, workspace_root=workspace)
    state.active_screen = _load_persisted_active_screen(selected)
    console.print(f"[green]Active project:[/green] {selected.as_posix()}")


def _wizard_pick_screen(ctx: typer.Context, manifest: BatchManifest) -> str:
    """Show a numbered screen list and return the picked feature slug."""
    from figma_flutter_agent.wizard.prompts import prompt_choice
    from figma_flutter_agent.wizard.state import (
        _persist_active_screen,
        _wizard_active_screen_label,
    )

    active = _wizard_active_screen_label(ctx)
    options = [screen.feature for screen in manifest.screens]
    if not options:
        msg = "No screens in screens.yaml"
        raise ValueError(msg)
    default = active if active in options else options[0]
    title = (
        f"Select active screen (current: {active})"
        if active is not None
        else "Select active screen"
    )
    picked = prompt_choice(title, options, default=default)
    _persist_active_screen(ctx, picked)
    return picked


def _wizard_select_active_screen(ctx: typer.Context) -> None:
    """Pick active screen from the manifest and return to the main menu."""
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.dev.project import (
        ensure_project_config,
        resolve_manifest_path,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    root = _wizard_project_dir(ctx)
    ensure_project_config(root)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    screen = _wizard_pick_screen(ctx, manifest)
    console.print(f"[green]Active screen:[/green] {screen}")


def _wizard_generate(ctx: typer.Context) -> None:
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import _figma_url_for_screen, _resolve_dump
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import (
        ensure_project_config,
        resolve_manifest_path,
    )
    from figma_flutter_agent.figma.url import FigmaUrlKind
    from figma_flutter_agent.wizard.prompts import (
        ensure_llm_generation_ready,
        print_pipeline_warnings,
        prompt_confirm,
        prompt_figma_input,
        prompt_screen_name,
        prompt_text,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir
    from figma_flutter_agent.pipeline.run import run_pipeline

    root = _wizard_project_dir(ctx)
    config_path = ensure_project_config(root)
    use_dump = prompt_confirm("Use cached .figma_debug dump (offline)?", default=True)
    from_dump: Path | None = None
    figma_url: str
    feature_name: str | None = None
    if use_dump:
        manifest = load_batch_manifest(resolve_manifest_path(root))
        screen = prompt_screen_name(ctx, manifest)
        entry = next(item for item in manifest.screens if item.feature == screen)
        from_dump = _resolve_dump(entry, manifest.project_dir)
        figma_url = _figma_url_for_screen(manifest, entry)
        feature_name = screen
    else:
        parsed = prompt_figma_input(
            expect_kind=FigmaUrlKind.FRAME,
            ctx=ctx,
            project_dir=root,
        )
        if parsed is None:
            msg = "Frame URL prompt returned no input"
            raise RuntimeError(msg)
        from figma_flutter_agent.figma.url import build_figma_url

        figma_url = build_figma_url(parsed.file_key, parsed.node_id or "")
        raw_feature = prompt_text("Feature folder name (Enter = auto)", default="")
        feature_name = raw_feature or None
    settings = load_settings(config_path)
    ensure_llm_generation_ready(settings)
    force_llm_regen = True
    console.print("[dim]Codegen:[/dim] LLM screen IR + emitter")
    result = asyncio.run(
        run_pipeline(
            settings,
            figma_url=figma_url,
            project_dir=root,
            feature_name=feature_name,
            from_dump=from_dump,
            require_figma_token=from_dump is None,
            force_llm_regen=force_llm_regen,
        )
    )
    print_pipeline_warnings(result.warnings)
    console.print("[green]Generation complete.[/green]")


def _wizard_fetch_from_figma(
    ctx: typer.Context, *, parsed: ParsedFigmaInput | None = None
) -> None:
    """Import one frame or dump a full Figma file based on pasted URL."""
    from figma_flutter_agent.dev.project import ensure_project_config
    from figma_flutter_agent.figma.url import FigmaUrlKind
    from figma_flutter_agent.wizard.menus import (
        _file_fetch_menu_options,
        _prompt_import_manifest_mode,
    )
    from figma_flutter_agent.wizard.prompts import (
        _menu_command,
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
        frame_fetch_menu_options,
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
        frame_fetch_menu_options(),
        default=frame_fetch_menu_options()[0],
    )
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
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice

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


def _wizard_rename_screen(ctx: typer.Context) -> None:
    from figma_flutter_agent.batch.manifest import (
        format_screen_list,
        load_batch_manifest,
        rename_screen_in_manifest,
    )
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.wizard.prompts import (
        prompt_screen_name,
        prompt_text,
    )
    from figma_flutter_agent.wizard.state import (
        _persist_active_screen,
        _wizard_active_screen_label,
        _wizard_project_dir,
        _wizard_state,
    )

    root = _wizard_project_dir(ctx)
    manifest_path = resolve_manifest_path(root)
    manifest = load_batch_manifest(manifest_path)
    if not manifest.screens:
        console.print("[yellow]No screens in screens.yaml.[/yellow]")
        return
    active = _wizard_active_screen_label(ctx)
    console.print(format_screen_list(manifest, active=active))
    old_slug = prompt_screen_name(ctx, manifest)
    new_raw = prompt_text(f"New slug for {old_slug!r}", default="").strip()
    if not new_raw:
        console.print("[yellow]Rename canceled.[/yellow]")
        return
    try:
        _, previous, renamed = rename_screen_in_manifest(manifest_path, old_slug, new_raw)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return
    state = _wizard_state(ctx)
    if state.active_screen == previous:
        _persist_active_screen(ctx, renamed)
    console.print(f"[green]Renamed screen[/green] {previous} → {renamed}")


def _wizard_export_screen_assets(ctx: typer.Context) -> None:
    """Export SVG/PNG assets for one screen from its cached dump (Images API only)."""
    import asyncio
    import json

    from figma_flutter_agent.batch.asset_export import (
        asset_export_gap_hint,
        count_exportable_assets,
        export_screen_assets_from_dump,
        resolve_screen_dump_path,
    )
    from figma_flutter_agent.batch.manifest import format_screen_list, load_batch_manifest
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
    from figma_flutter_agent.figma.client import FigmaConnector
    from figma_flutter_agent.wizard.prompts import prompt_screen_name
    from figma_flutter_agent.wizard.state import (
        _wizard_active_screen_label,
        _wizard_project_dir,
    )

    root = _wizard_project_dir(ctx)
    ensure_project_config(root)
    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)

    manifest_path = resolve_manifest_path(root)
    manifest = load_batch_manifest(manifest_path)
    if not manifest.screens:
        console.print("[yellow]No screens in screens.yaml.[/yellow]")
        return

    active = _wizard_active_screen_label(ctx)
    console.print(format_screen_list(manifest, active=active))
    slug = prompt_screen_name(ctx, manifest)
    screen = next(item for item in manifest.screens if item.feature == slug)
    dump_path = resolve_screen_dump_path(screen, manifest.project_dir)
    if not dump_path.is_file():
        console.print(f"[red]No cached dump:[/red] {dump_path.as_posix()}")
        return

    document = json.loads(dump_path.read_text(encoding="utf-8"))
    expected_icons, expected_raster = count_exportable_assets(document, settings.agent.assets)
    console.print(
        f"Dump has {expected_icons} SVG icon(s) and {expected_raster} raster asset(s) to export."
    )

    async def _run() -> object:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            return await export_screen_assets_from_dump(
                connector,
                manifest=manifest,
                screen=screen,
                assets=settings.agent.assets,
            )

    result = asyncio.run(_run())
    console.print(
        f"[green]Assets exported[/green] {slug}: "
        f"{result.icon_count} SVG, {result.raster_count} raster"
    )
    gap_hint = asset_export_gap_hint(document, settings.agent.assets, result)
    if gap_hint:
        console.print(f"[yellow]{gap_hint}[/yellow]")


def _wizard_batch_generate(ctx: typer.Context) -> None:
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.batch.run import run_batch_generate
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import ensure_project_config
    from figma_flutter_agent.wizard.prompts import (
        ensure_llm_generation_ready,
        prompt_manifest_path,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir

    root = _wizard_project_dir(ctx)
    config_path = ensure_project_config(root)
    manifest_path = prompt_manifest_path(ctx, root)
    manifest = load_batch_manifest(manifest_path)
    settings = load_settings(config_path)
    ensure_llm_generation_ready(settings)
    force_llm_regen = True
    report = asyncio.run(
        run_batch_generate(
            manifest,
            settings,
            allow_dev_profile=True,
            force_llm_regen=force_llm_regen,
        )
    )
    if report.passed:
        console.print(f"[green]Batch OK[/green] ({len(report.results)} screens)")
    else:
        console.print(f"[red]Batch failed[/red] ({len(report.failures)} failures)")
        raise typer.Exit(code=1)


def _wizard_list_screens(ctx: typer.Context) -> None:
    from figma_flutter_agent.wizard.menus import _list_menu_options
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice

    mode_label = prompt_choice(
        "List mode",
        _list_menu_options(),
        default=_list_menu_options()[0],
    )
    command = _menu_command(mode_label)
    if command == "delete":
        _wizard_delete_screens(ctx)
    elif command == "rename":
        _wizard_rename_screen(ctx)
    elif command == "assets":
        _wizard_export_screen_assets(ctx)
    else:
        _wizard_list_screens_view(ctx)


def _wizard_list_screens_view(ctx: typer.Context) -> None:
    from figma_flutter_agent.batch.manifest import (
        format_screen_list,
        load_batch_manifest,
    )
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.dev.wizard import (
        build_run_plan,
        collect_screen_preflight,
        format_screen_preflight,
    )
    from figma_flutter_agent.wizard.prompts import prompt_confirm
    from figma_flutter_agent.wizard.state import (
        _wizard_active_screen_label,
        _wizard_project_dir,
    )

    root = _wizard_project_dir(ctx)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    active = _wizard_active_screen_label(ctx)
    console.print(format_screen_list(manifest, active=active))
    if active is not None:
        try:
            plan = build_run_plan(project_dir=root, screen_name=active)
            console.print("")
            console.print(format_screen_preflight(collect_screen_preflight(plan)))
            ux_report = root / ".figma_debug" / "reports" / f"{active}_ai_ux.json"
            if ux_report.is_file():
                console.print(f"AI UX report: {ux_report.as_posix()}")
        except (FileNotFoundError, ValueError):
            pass
    if prompt_confirm("Select a different active screen?", default=False):
        _wizard_select_active_screen(ctx)


def _wizard_delete_screens(ctx: typer.Context) -> None:
    from figma_flutter_agent.batch.manifest import (
        format_screen_list,
        load_batch_manifest,
        remove_screens_from_manifest,
    )
    from figma_flutter_agent.dev.project import resolve_manifest_path
    from figma_flutter_agent.wizard.prompts import prompt_text
    from figma_flutter_agent.wizard.state import (
        _persist_active_screen,
        _wizard_active_screen_label,
        _wizard_project_dir,
        _wizard_state,
    )

    root = _wizard_project_dir(ctx)
    manifest_path = resolve_manifest_path(root)
    manifest = load_batch_manifest(manifest_path)
    active = _wizard_active_screen_label(ctx)
    console.print(format_screen_list(manifest, active=active))
    raw = prompt_text("Slugs to delete (comma-separated)", default="").strip()
    if not raw:
        console.print("[yellow]Nothing to delete.[/yellow]")
        return
    names = [part.strip() for part in raw.split(",") if part.strip()]
    try:
        updated, removed = remove_screens_from_manifest(manifest_path, names)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return
    state = _wizard_state(ctx)
    if state.active_screen in removed:
        _persist_active_screen(ctx, None)
    console.print(
        f"[green]Removed {len(removed)} screen(s):[/green] {', '.join(removed)} "
        f"({len(updated.screens)} remaining)"
    )


def _wizard_live_check(ctx: typer.Context) -> None:
    import asyncio

    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.figma.client import FigmaConnector
    from figma_flutter_agent.figma.url import FigmaUrlKind
    from figma_flutter_agent.wizard.prompts import (
        prompt_confirm,
        prompt_figma_input,
    )
    from figma_flutter_agent.wizard.state import _wizard_project_dir
    from figma_flutter_agent.stages.fetch import fetch_figma_frame

    configure_logging = __import__(
        "figma_flutter_agent.logging_setup",
        fromlist=["configure_logging"],
    ).configure_logging
    configure_logging(verbose=False)
    settings = load_settings()
    token = settings.figma_token().strip()
    if not token:
        console.print("[red]FIGMA_ACCESS_TOKEN is not set[/red]")
        raise typer.Exit(code=1)
    console.print("[green]FIGMA_ACCESS_TOKEN[/green] present")
    project_dir = _wizard_project_dir(ctx)
    parsed = prompt_figma_input(
        ctx=ctx,
        project_dir=project_dir,
        expect_kind=FigmaUrlKind.FRAME,
        optional=True,
    )
    dump = prompt_confirm("Write raw dump to .figma_debug?", default=False)
    if parsed is None:
        console.print(
            "[yellow]No frame URL — configure screens.yaml, FIGMA_DEFAULT_URL, "
            "or FIGMA_SMOKE_* to smoke-test fetch.[/yellow]"
        )
        raise typer.Exit(code=0)
    file_key = parsed.file_key
    node_id = parsed.node_id or ""

    async def _run_fetch() -> None:
        async with FigmaConnector(token, settings.figma_api_base_url) as connector:
            result = await fetch_figma_frame(
                connector,
                file_key=file_key,
                node_id=node_id,
                project_dir=project_dir,
                verbose=dump,
            )
        console.print(
            f"[green]Live fetch OK[/green] frame={result.root.get('name')!r} "
            f"links={len(result.prototype_links)}"
        )

    asyncio.run(_run_fetch())

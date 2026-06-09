"""Wizard screen management action handlers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

if TYPE_CHECKING:
    from figma_flutter_agent.batch.manifest import BatchManifest

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

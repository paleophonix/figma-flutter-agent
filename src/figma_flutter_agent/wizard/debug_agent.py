"""Wizard OpenCode agent debug for the active screen."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

console = Console()


def _wizard_debug(ctx: typer.Context) -> None:
    """Debug the selected screen using cached or refreshed debug artifacts."""
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.debug.context import collect_screen_debug_context
    from figma_flutter_agent.debug.paths import debug_path_display
    from figma_flutter_agent.dev.opencode.client import OpenCodeClient
    from figma_flutter_agent.dev.opencode.runtime import ensure_opencode_serve
    from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
    from figma_flutter_agent.dev.wizard.preflight import build_run_plan, collect_screen_preflight
    from figma_flutter_agent.dev.wizard.sync import generate_screen_for_preview
    from figma_flutter_agent.wizard.menus import _is_menu_return, _run_menu_options
    from figma_flutter_agent.wizard.prompts import (
        _menu_command,
        ensure_llm_generation_ready,
        prompt_choice,
    )
    from figma_flutter_agent.wizard.screens import _wizard_resolve_screen
    from figma_flutter_agent.wizard.state import _persist_active_screen, _wizard_project_dir

    mode_label = prompt_choice(
        "Debug pipeline",
        _run_menu_options(),
        default=_run_menu_options()[0],
    )
    if _is_menu_return(mode_label):
        return
    command = _menu_command(mode_label)

    root = _wizard_project_dir(ctx)
    config_path = ensure_project_config(root)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    screen = _wizard_resolve_screen(ctx, manifest)
    _persist_active_screen(ctx, screen)
    plan = build_run_plan(project_dir=root, screen_name=screen)
    preflight = collect_screen_preflight(plan)
    settings = load_settings(config_path)

    if command == "ir-offline":
        if not preflight.dump_exists:
            raise FileNotFoundError(
                f"Dump missing for {screen}: {plan.dump_path.as_posix()}. "
                "Run batch dump-file or fetch first."
            )
        console.print(
            "[dim]Debug mode:[/dim] ir-offline — cached debug bundle only (no regenerate)"
        )
    elif command == "full":
        ensure_llm_generation_ready(settings)
        console.print("[dim]Debug mode:[/dim] full — regenerate from live Figma")
        asyncio.run(
            generate_screen_for_preview(
                plan,
                settings,
                live=True,
                force_llm_regen=True,
            )
        )
    elif command == "offline":
        if not preflight.dump_exists:
            raise FileNotFoundError(
                f"Dump missing for {screen}: {plan.dump_path.as_posix()}. "
                "Run batch dump-file or fetch first."
            )
        ensure_llm_generation_ready(settings)
        console.print("[dim]Debug mode:[/dim] offline — regenerate from cached dump")
        asyncio.run(
            generate_screen_for_preview(
                plan,
                settings,
                live=False,
                force_llm_regen=True,
            )
        )
    else:
        console.print(f"[yellow]Unknown debug mode:[/yellow] {command}")
        return

    bundle = collect_screen_debug_context(plan.project_dir, plan.screen.feature)
    display_root = debug_path_display(bundle.screen_root, plan.project_dir)
    console.print(f"[bold]Screen[/bold] {plan.screen.feature}")
    console.print(f"[dim]Debug root:[/dim] {display_root}")
    console.print(
        f"[dim]Artifacts:[/dim] {len(bundle.present_files)} present "
        f"({', '.join(bundle.present_files)})"
    )
    if bundle.log_tail:
        tail_lines = len(bundle.log_tail.splitlines())
        console.print(f"[dim]last.log tail:[/dim] {tail_lines} line(s) loaded")

    serve = asyncio.run(
        ensure_opencode_serve(
            base_url=settings.opencode_base_url,
            password=settings.opencode_server_password.get_secret_value(),
        )
    )
    if serve.started_locally:
        console.print(f"[green]OpenCode serve started[/green] at {serve.base_url}")
    else:
        console.print(f"[green]OpenCode serve ready[/green] at {serve.base_url}")

    client = OpenCodeClient(
        base_url=settings.opencode_base_url,
        password=settings.opencode_server_password.get_secret_value(),
    )

    async def _create_debug_session() -> str:
        return await client.create_session(title=f"debug-{plan.screen.feature}")

    session_id = asyncio.run(_create_debug_session())
    console.print(f"[green]OpenCode session[/green] {session_id}")
    console.print("[dim]Agent prompt/skills wiring is a follow-up.[/dim]")

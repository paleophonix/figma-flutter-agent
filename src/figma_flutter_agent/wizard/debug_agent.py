"""Wizard OpenCode agent debug for the active screen."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

console = Console()


def _wizard_debug(ctx: typer.Context) -> None:
    """Run the repair pipeline on existing ``.debug`` artifacts (no regenerate)."""
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.debug.context import collect_screen_debug_context
    from figma_flutter_agent.debug.paths import debug_path_display
    from figma_flutter_agent.dev.opencode import (
        OpenCodeClient,
        build_opencode_overlay,
        ensure_opencode_serve,
        evaluate_run_gate,
        run_repair_pipeline,
    )
    from figma_flutter_agent.dev.opencode.failure_class import FailureClass
    from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
    from figma_flutter_agent.dev.wizard.preflight import build_run_plan
    from figma_flutter_agent.wizard.screens import _wizard_resolve_screen
    from figma_flutter_agent.wizard.state import _persist_active_screen, _wizard_project_dir

    root = _wizard_project_dir(ctx)
    config_path = ensure_project_config(root)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    screen = _wizard_resolve_screen(ctx, manifest)
    _persist_active_screen(ctx, screen)
    plan = build_run_plan(project_dir=root, screen_name=screen)
    settings = load_settings(config_path)

    console.print(
        "[dim]Debug pipeline:[/dim] existing .debug artifacts only (no generate)"
    )

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

    gate = evaluate_run_gate(plan.project_dir, plan.screen.feature)
    console.print(
        f"[bold]Run Gate[/bold] {gate.verdict.value} "
        f"case_mode={gate.case_mode} board={gate.agent_board}"
    )
    if gate.verdict in {FailureClass.NO_SERVE, FailureClass.UNKNOWN_BLOCKED}:
        console.print("[yellow]Pipeline stopped at Run Gate.[/yellow]")
        return

    serve = asyncio.run(
        ensure_opencode_serve(
            base_url=settings.opencode_base_url,
            password=settings.opencode_server_password.get_secret_value(),
            config_overlay=build_opencode_overlay(settings.agent.debug_pipeline),
        )
    )
    if serve.started_locally:
        console.print(f"[green]OpenCode serve started[/green] at {serve.base_url}")
    else:
        console.print(f"[green]OpenCode serve ready[/green] at {serve.base_url}")

    opencode = OpenCodeClient(
        base_url=settings.opencode_base_url,
        password=settings.opencode_server_password.get_secret_value(),
    )

    async def _run() -> None:
        outcome = await run_repair_pipeline(
            settings=settings,
            project_dir=plan.project_dir,
            feature=plan.screen.feature,
            opencode_client=opencode,
            skip_opencode_repair=False,
        )
        if outcome.stopped:
            console.print(f"[yellow]Pipeline stopped:[/yellow] {outcome.stop_reason}")
            if outcome.stop_reason.startswith("user_declined_"):
                console.print("[dim]Step confirmation declined.[/dim]")
        if outcome.workspace is not None:
            console.print(f"[dim]Worktree:[/dim] {outcome.workspace.worktree.as_posix()}")
            console.print(f"[dim]State:[/dim] {outcome.workspace.state_dir.as_posix()}")
        if outcome.summarize_blocked:
            console.print("[dim]Summarize blocked (review LOOP).[/dim]")

    asyncio.run(_run())

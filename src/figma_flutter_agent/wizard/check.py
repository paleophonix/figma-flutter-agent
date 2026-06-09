"""Wizard check/doctor/live-check action handlers."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def _wizard_print_font_audit(ctx: typer.Context) -> bool:
    """Print font diagnostics for the current Flutter project. Returns False when any row fails."""
    from figma_flutter_agent.fonts.diagnostics import format_wizard_font_report
    from figma_flutter_agent.wizard.state import (
        _wizard_active_screen_label,
        _wizard_project_dir,
    )
    from figma_flutter_agent.wizard.screens import _wizard_resolve_active_dump

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

"""Wizard OpenCode agent debug for the active screen."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from loguru import logger
from rich.console import Console

from figma_flutter_agent.logging_setup import configure_logging
from figma_flutter_agent.observability.loki_sink import LOKI_APP_DEBUG, LOKI_TEAM_DEFAULT

if TYPE_CHECKING:
    from figma_flutter_agent.dev.opencode.worktree_catalog import RepairWorktreeEntry

console = Console()


def _debug_log(message: str, **extra: object) -> None:
    """Mirror wizard debug progress into Loguru (and Loki when configured)."""
    logger.bind(
        pipeline="repair",
        command="wizard_debug",
        app=LOKI_APP_DEBUG,
        team=LOKI_TEAM_DEFAULT,
        **extra,
    ).info(message)


def _prompt_repair_worktree(
    *,
    repo: Path,
    project_label: str,
    feature: str,
) -> RepairWorktreeEntry | None:
    """Prompt for a repair worktree filtered by project and screen."""
    from figma_flutter_agent.dev.opencode.worktree_catalog import list_repair_worktrees_for_screen
    from figma_flutter_agent.wizard.prompts import prompt_choice

    entries = list_repair_worktrees_for_screen(
        repo,
        project_label=project_label,
        feature=feature,
    )
    if not entries:
        console.print(
            f"[yellow]No repair worktrees for {project_label}/{feature}.[/yellow] "
            "Use [bold]new[/bold] first."
        )
        return None
    labels = [entry.menu_label for entry in entries]
    picked = prompt_choice("Repair worktree", labels, default=labels[0])
    index = labels.index(picked)
    return entries[index]


def _print_debug_screen_header(
    *,
    feature: str,
    display_root: str,
    bundle_present: int,
    present_files: list[str],
    log_tail: str | None,
) -> None:
    """Print active screen and artifact summary."""
    _debug_log(f"Screen {feature}", feature=feature)
    _debug_log(f"Debug root: {display_root}")
    console.print(f"[bold]Screen[/bold] {feature}")
    console.print(f"[dim]Debug root:[/dim] {display_root}")
    console.print(
        f"[dim]Artifacts:[/dim] {bundle_present} present "
        f"({', '.join(present_files)})"
    )
    if log_tail:
        tail_lines = len(log_tail.splitlines())
        console.print(f"[dim]last.log tail:[/dim] {tail_lines} line(s) loaded")


def _ensure_opencode_serve(settings) -> None:
    """Start or verify OpenCode serve for the repair pipeline."""
    from figma_flutter_agent.dev.opencode import build_opencode_overlay, ensure_opencode_serve

    serve = asyncio.run(
        ensure_opencode_serve(
            base_url=settings.opencode_base_url,
            password=settings.opencode_server_password.get_secret_value(),
            config_overlay=build_opencode_overlay(settings.agent.debug_pipeline),
        )
    )
    if serve.started_locally:
        _debug_log(f"OpenCode serve started at {serve.base_url}")
        console.print(f"[green]OpenCode serve started[/green] at {serve.base_url}")
    else:
        _debug_log(f"OpenCode serve ready at {serve.base_url}")
        console.print(f"[green]OpenCode serve ready[/green] at {serve.base_url}")

    if settings.agent.debug_pipeline.fusion_escalation and settings.agent.debug_pipeline.board_models:
        _debug_log("Fusion escalation from round 2 on recognise/diagnose/review")
        console.print(
            "[dim]Fusion escalation from correction round 2 on recognise/diagnose/review "
            "(panel grows each round; first Fusion step may take several minutes).[/dim]"
        )


def _print_pipeline_outcome(outcome, settings) -> None:
    """Print repair pipeline completion summary."""
    stop_hints = {
        "repair_noop": (
            "OpenCode repair finished without editing plan compiler targetFiles. "
            "Plan was revised until loop budget exhausted — check .repair/state/plan.json "
            "and re-run debug → continue."
        ),
        "plan_invalid_targets": (
            "Plan named targetFiles that do not exist under src/figma_flutter_agent/. "
            "See plan_validation_error in .repair/state/ and compiler_path_catalog in prompts."
        ),
        "repair_gates_failed": "Repair diff failed ruff/pytest gates in the worktree.",
        "budget_exhausted": "Outer correction loop budgets exhausted.",
    }
    if outcome.stopped:
        _debug_log(f"Pipeline stopped: {outcome.stop_reason}", stop_reason=outcome.stop_reason)
        console.print(f"[yellow]Pipeline stopped:[/yellow] {outcome.stop_reason}")
        hint = stop_hints.get(str(outcome.stop_reason or ""))
        if hint:
            console.print(f"[dim]{hint}[/dim]")
        if outcome.stop_reason.startswith("user_declined_"):
            console.print("[dim]Step confirmation declined.[/dim]")
    if outcome.workspace is not None:
        console.print(f"[dim]Worktree:[/dim] {outcome.workspace.worktree.as_posix()}")
        console.print(f"[dim]State:[/dim] {outcome.workspace.state_dir.as_posix()}")
    if outcome.summarize_blocked:
        console.print("[dim]Summarize blocked (review LOOP).[/dim]")
    retain = settings.agent.debug_pipeline.worktrees.retain_latest
    if retain == 0:
        console.print("[dim]Worktree retention: 0 (ephemeral runs are removed after exit).[/dim]")
    elif retain == 1:
        console.print("[dim]Older repair worktrees were pruned; latest kept for merge.[/dim]")


async def _run_repair_pipeline_async(
    *,
    settings,
    project_dir: Path,
    feature: str,
    opencode_client,
    existing_workspace=None,
    resume: bool = False,
):
    """Run repair pipeline and print wizard outcome."""
    from figma_flutter_agent.dev.opencode import run_repair_pipeline

    outcome = await run_repair_pipeline(
        settings=settings,
        project_dir=project_dir,
        feature=feature,
        opencode_client=opencode_client,
        skip_opencode_repair=False,
        existing_workspace=existing_workspace,
        resume=resume,
    )
    _print_pipeline_outcome(outcome, settings)
    return outcome


def _wizard_debug_run_from_worktree(
    ctx: typer.Context,
    *,
    project_dir: Path,
    feature: str,
    project_label: str,
    settings,
) -> None:
    """Deploy a worktree debug bundle and launch Flutter."""
    from figma_flutter_agent.config import apply_interactive_preview_profile
    from figma_flutter_agent.config.paths import agent_repo_root
    from figma_flutter_agent.dev.debug_view import launch_debug_view
    from figma_flutter_agent.dev.opencode.worktree_catalog import resolve_worktree_screen_bundle
    from figma_flutter_agent.dev.wizard import resolve_flutter_device_id_from_settings

    entry = _prompt_repair_worktree(
        repo=agent_repo_root(),
        project_label=project_label,
        feature=feature,
    )
    if entry is None:
        return

    try:
        bundle_path = resolve_worktree_screen_bundle(entry.worktree)
    except FileNotFoundError as exc:
        console.print(f"[red]Bundle missing:[/red] {exc}")
        return

    console.print(f"[dim]Worktree:[/dim] {entry.worktree.as_posix()}")
    console.print(f"[dim]Bundle:[/dim] {bundle_path.as_posix()}")
    preview_settings = apply_interactive_preview_profile(settings)
    device_id = resolve_flutter_device_id_from_settings(preview_settings)
    launched = launch_debug_view(
        project_dir,
        feature_name=feature,
        bundle_path=bundle_path,
        device_id=device_id,
        settings=preview_settings,
    )
    if launched is False:
        console.print(f"[yellow]Preview stopped[/yellow] — {feature}")
    else:
        console.print(f"[green]Preview launched[/green] — {feature} (worktree {entry.case_id})")


def _wizard_debug(ctx: typer.Context) -> None:
    """Run the repair pipeline on existing ``.debug`` artifacts (no regenerate)."""
    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.config.paths import agent_repo_root
    from figma_flutter_agent.debug.context import collect_screen_debug_context
    from figma_flutter_agent.debug.paths import debug_path_display, screen_debug_safe_project
    from figma_flutter_agent.dev.opencode import OpenCodeClient, evaluate_run_gate
    from figma_flutter_agent.dev.opencode.failure_class import FailureClass
    from figma_flutter_agent.dev.opencode.workspace import load_repair_workspace
    from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
    from figma_flutter_agent.dev.wizard.preflight import build_run_plan
    from figma_flutter_agent.wizard.menus import _debug_menu_options, _is_menu_return
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice
    from figma_flutter_agent.wizard.screens import _wizard_resolve_screen
    from figma_flutter_agent.wizard.state import _persist_active_screen, _wizard_project_dir

    mode_label = prompt_choice(
        "Debug mode",
        _debug_menu_options(),
        default=_debug_menu_options()[0],
    )
    if _is_menu_return(mode_label):
        return
    mode = _menu_command(mode_label)

    root = _wizard_project_dir(ctx)
    config_path = ensure_project_config(root)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    screen = _wizard_resolve_screen(ctx, manifest)
    _persist_active_screen(ctx, screen)
    plan = build_run_plan(project_dir=root, screen_name=screen)
    settings = load_settings(config_path)
    configure_logging(verbose=False, settings=settings)
    project_label = screen_debug_safe_project(root)

    _debug_log("Wizard debug: existing .debug artifacts only (no generate)")
    console.print(
        "[dim]Debug pipeline:[/dim] existing .debug artifacts only (no generate)"
    )

    bundle = collect_screen_debug_context(plan.project_dir, plan.screen.feature)
    display_root = debug_path_display(bundle.screen_root, plan.project_dir)
    _print_debug_screen_header(
        feature=plan.screen.feature,
        display_root=display_root,
        bundle_present=len(bundle.present_files),
        present_files=bundle.present_files,
        log_tail=bundle.log_tail,
    )

    if mode == "run":
        _wizard_debug_run_from_worktree(
            ctx,
            project_dir=plan.project_dir,
            feature=plan.screen.feature,
            project_label=project_label,
            settings=settings,
        )
        return

    gate = evaluate_run_gate(plan.project_dir, plan.screen.feature)
    _debug_log(
        f"Run Gate {gate.verdict.value} case_mode={gate.case_mode} board={gate.agent_board}",
        gate_verdict=gate.verdict.value,
        case_mode=gate.case_mode,
        agent_board=gate.agent_board,
    )
    console.print(
        f"[bold]Run Gate[/bold] {gate.verdict.value} "
        f"case_mode={gate.case_mode} board={gate.agent_board}"
    )
    if gate.verdict in {FailureClass.NO_SERVE, FailureClass.UNKNOWN_BLOCKED}:
        _debug_log("Pipeline stopped at Run Gate", stopped=True)
        console.print("[yellow]Pipeline stopped at Run Gate.[/yellow]")
        return

    existing_workspace = None
    resume = False
    if mode == "continue":
        entry = _prompt_repair_worktree(
            repo=agent_repo_root(),
            project_label=project_label,
            feature=plan.screen.feature,
        )
        if entry is None:
            return
        try:
            existing_workspace = load_repair_workspace(entry.worktree)
        except FileNotFoundError as exc:
            console.print(f"[red]Worktree invalid:[/red] {exc}")
            return
        resume = True
        console.print(f"[dim]Resuming worktree:[/dim] {entry.case_id}")

    _ensure_opencode_serve(settings)

    opencode = OpenCodeClient(
        base_url=settings.opencode_base_url,
        password=settings.opencode_server_password.get_secret_value(),
    )

    asyncio.run(
        _run_repair_pipeline_async(
            settings=settings,
            project_dir=plan.project_dir,
            feature=plan.screen.feature,
            opencode_client=opencode,
            existing_workspace=existing_workspace,
            resume=resume,
        )
    )

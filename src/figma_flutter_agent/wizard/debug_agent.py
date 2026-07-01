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
    console.print(f"[dim]Artifacts:[/dim] {bundle_present} present ({', '.join(present_files)})")
    if log_tail:
        tail_lines = len(log_tail.splitlines())
        console.print(f"[dim]last.log tail:[/dim] {tail_lines} line(s) loaded")


def _ensure_opencode_serve(settings) -> None:
    """Start or verify OpenCode serve for the repair pipeline."""
    from figma_flutter_agent.dev.opencode import build_opencode_overlay, ensure_opencode_serve
    from figma_flutter_agent.dev.opencode.opencode_policy import prompt_options_for_write_step
    from figma_flutter_agent.dev.opencode.provider_preflight import (
        verify_opencode_openrouter_connectivity,
    )
    from figma_flutter_agent.errors import LlmError

    api_key = settings.openrouter_api_key.get_secret_value().strip()
    if not api_key:
        raise LlmError(
            "OPENROUTER_API_KEY is required for wizard debug repair/fix "
            "(OpenCode serve calls OpenRouter separately from plan/recognise steps)."
        )

    serve = asyncio.run(
        ensure_opencode_serve(
            base_url=settings.opencode_base_url,
            password=settings.opencode_server_password.get_secret_value(),
            config_overlay=build_opencode_overlay(
                settings.agent.debug_pipeline,
                openrouter_api_key=api_key,
            ),
            openrouter_api_key=api_key,
            restart_with_overlay=True,
        )
    )
    if serve.restarted:
        _debug_log(f"OpenCode serve restarted with overlay at {serve.base_url}")
        console.print(
            f"[green]OpenCode serve restarted[/green] with debug_pipeline overlay at {serve.base_url}"
        )
    elif serve.started_locally:
        _debug_log(f"OpenCode serve started at {serve.base_url}")
        console.print(f"[green]OpenCode serve started[/green] at {serve.base_url}")
    else:
        _debug_log(f"OpenCode serve ready at {serve.base_url}")
        console.print(f"[green]OpenCode serve ready[/green] at {serve.base_url}")
        console.print(
            "[dim]If repair/fix fail with ProviderAuthError, stop OpenCode on :4096 and re-run "
            "debug so serve inherits OPENROUTER_API_KEY from .env.[/dim]"
        )

    if (
        settings.agent.debug_pipeline.fusion_escalation
        and settings.agent.debug_pipeline.board_models
        and settings.agent.debug_pipeline.min_board_models > 1
    ):
        _debug_log(
            "Fusion escalation on recognise/diagnose/review from correction cycle 1 "
            f"(min_board_models={settings.agent.debug_pipeline.min_board_models}, "
            f"max_board_models={settings.agent.debug_pipeline.max_board_models}; "
            "not plan/repair retries)"
        )
        console.print(
            "[dim]Fusion on recognise/diagnose/review from cycle 1 when "
            f"min_board_models={settings.agent.debug_pipeline.min_board_models} "
            "(set min_board_models: 1 for base-model-only).[/dim]"
        )

    repair_prompt = prompt_options_for_write_step(settings.agent.debug_pipeline, step="repair")
    asyncio.run(
        verify_opencode_openrouter_connectivity(
            base_url=settings.opencode_base_url,
            password=settings.opencode_server_password.get_secret_value(),
            model=str(repair_prompt["model"]),
            reasoning_effort=repair_prompt["reasoning_effort"],
        )
    )
    console.print(f"[green]OpenCode → OpenRouter preflight OK[/green] ({repair_prompt['model']})")


def _print_pipeline_outcome(outcome, settings) -> None:
    """Print repair pipeline completion summary."""
    stop_hints = {
        "repair_noop": (
            "OpenCode repair finished without editing plan compiler targetFiles and the "
            "plan had no actionable compiler targets. Read .repair/state/plan.json; revise "
            "plan targetFiles or restart with a narrower law."
        ),
        "repair_incomplete": (
            "OpenCode hit agent.steps before editing compiler files after repair retries. "
            "Increase debug_pipeline.loops.max_opencode_repair_steps, restart OpenCode serve "
            "on :4096, and resume the worktree — do not rerun recognise from scratch."
        ),
        "opencode_prompt_timeout": (
            "OpenCode repair prompt exceeded debug_pipeline.loops.opencode_prompt_timeout_sec. "
            "Check OPENROUTER_API_KEY, OpenCode serve logs, and .debug/agent/.../trace/ — then resume "
            "the worktree instead of starting new."
        ),
        "opencode_provider_error": (
            "OpenCode repair/fix could not reach OpenRouter (missing OPENROUTER_API_KEY in the "
            "serve process). Stop the process on :4096 and re-run wizard debug so serve restarts "
            "with your .env key."
        ),
        "plan_invalid_targets": (
            "Plan failed structural validation after retries (missing steps, tests, or bad "
            "targetFiles). See plan_validation_error in run_context and .repair/state/plan.json."
        ),
        "plan_blocked": (
            "Plan returned blocked=true with no actionable CODE_CHANGE steps and worktree "
            "salvage could not adopt pending compiler edits (gates failed or no diff). "
            "Read .repair/state/plan.json blockedItems and repair.json gates output."
        ),
        "diagnose_empty_laws": (
            "Diagnose returned laws[] empty while inspect anchored compiler repoPaths. "
            "Re-run debug after checking diagnose prompt/trace; FORENSIC requires emitter laws "
            "for PATCH_RUNTIME overflow even when recognise.blocked=true."
        ),
        "repair_no_plan_steps": (
            "Plan has no CODE_CHANGE steps with order fields for repair. Resume from plan or "
            "regenerate plan.json before repair."
        ),
        "regenerate_failed": (
            "Post-repair regenerate subprocess or debug mirror refresh failed. "
            "Read .repair/state/regenerate.json reason_code (MIRROR_REFRESH_FAILED, "
            "REGENERATE_TIMEOUT, PIPELINE_ERROR)."
        ),
        "repair_gates_failed": (
            "Repair compiler edits failed ruff/pytest in the worktree. "
            "Run poetry install --with dev in the worktree if imports fail; "
            "read .repair/state/repair.json gates output."
        ),
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
    from figma_flutter_agent.dev.opencode.run_gate import gate_blocks_pipeline
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
    console.print("[dim]Debug pipeline:[/dim] existing .debug artifacts only (no generate)")

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
    if gate_blocks_pipeline(verdict=gate.verdict, resume=resume):
        _debug_log("Pipeline stopped at Run Gate", stopped=True)
        console.print("[yellow]Pipeline stopped at Run Gate.[/yellow]")
        return

    _ensure_opencode_serve(settings)

    opencode = OpenCodeClient(
        base_url=settings.opencode_base_url,
        password=settings.opencode_server_password.get_secret_value(),
        timeout_sec=(
            float(settings.agent.debug_pipeline.loops.opencode_prompt_timeout_sec)
            if settings.agent.debug_pipeline.loops.opencode_prompt_timeout_sec is not None
            else None
        ),
    )

    from figma_flutter_agent.dev.opencode.repair_log import bind_repair_progress_sink

    with bind_repair_progress_sink(
        lambda step, message: console.print(f"[cyan]{step}[/cyan] [dim]{message}[/dim]")
    ):
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

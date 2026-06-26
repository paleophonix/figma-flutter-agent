"""Wizard debug-view and agent sign-off action handlers."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()

_VIEW_CAPTURE_MODES = frozenset({"preview", "full-review"})
_VIEW_COMBAT_MODES = frozenset({"renders", "full-renders"})
_VIEW_CHROME_MODES = frozenset({"full-review", "full-renders"})


def _wizard_debug_view(ctx: typer.Context) -> None:
    """Preview a cached bundle and/or write combat renders under ``.debug/renders/``."""
    import asyncio

    from figma_flutter_agent.batch.manifest import load_batch_manifest
    from figma_flutter_agent.config import apply_interactive_preview_profile, load_settings
    from figma_flutter_agent.dev.debug_view import (
        launch_debug_view,
        launch_project_screen_in_chrome,
    )
    from figma_flutter_agent.dev.project import ensure_project_config, resolve_manifest_path
    from figma_flutter_agent.dev.view_renders import (
        run_view_combat_renders,
        run_view_oracle_capture,
        run_view_preview_capture,
    )
    from figma_flutter_agent.dev.wizard import resolve_flutter_device_id_from_settings
    from figma_flutter_agent.preview import CaptureMode, resolve_capture_mode
    from figma_flutter_agent.wizard.menus import (
        _is_menu_return,
        _prompt_view_bundle_choice,
        _view_menu_options,
    )
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice
    from figma_flutter_agent.wizard.screens import _wizard_resolve_screen
    from figma_flutter_agent.wizard.state import (
        _persist_active_screen,
        _wizard_project_dir,
    )

    root = _wizard_project_dir(ctx)
    ensure_project_config(root)
    manifest = load_batch_manifest(resolve_manifest_path(root))
    screen = _wizard_resolve_screen(ctx, manifest)
    _persist_active_screen(ctx, screen)
    settings = apply_interactive_preview_profile(load_settings(ensure_project_config(root)))

    mode_label = prompt_choice(
        "View mode",
        _view_menu_options(),
        default=_view_menu_options()[0],
    )
    if _is_menu_return(mode_label):
        return
    mode = _menu_command(mode_label)

    if mode == "chrome":
        device_id = resolve_flutter_device_id_from_settings(settings)
        launched = launch_project_screen_in_chrome(
            root,
            feature_name=screen,
            device_id=device_id,
            settings=settings,
        )
        if launched is False:
            console.print(f"[yellow]Preview stopped[/yellow] — {screen}")
        else:
            console.print(f"[green]Chrome preview launched[/green] — {screen} (lib/)")
        return

    bundle_choice = _prompt_view_bundle_choice(root, screen)
    console.print(f"[dim]Bundle:[/dim] {bundle_choice.path.as_posix()}")
    capture_mode = resolve_capture_mode(settings)
    continue_after_capture_failure = mode in _VIEW_CHROME_MODES

    if mode in _VIEW_CAPTURE_MODES:
        if capture_mode is CaptureMode.PREVIEW:
            console.print(
                "[dim]Capturing browser preview PNG (runtime.default_capture_mode=preview)…[/dim]"
            )
            try:
                preview_path = run_view_preview_capture(
                    root,
                    feature_name=screen,
                    bundle_path=bundle_choice.path,
                    settings=settings,
                )
            except Exception as exc:
                console.print(f"[red]Preview capture failed:[/red] {exc}")
                if not continue_after_capture_failure:
                    raise typer.Exit(code=1) from exc
                console.print("[yellow]Continuing with Chrome launch only.[/yellow]")
            else:
                console.print(
                    f"[green]Preview capture saved[/green] → {preview_path.as_posix()}",
                )
        else:
            console.print(
                "[dim]Capturing oracle Flutter render (runtime.default_capture_mode=oracle)…[/dim]"
            )
            try:
                oracle_path = run_view_oracle_capture(
                    root,
                    feature_name=screen,
                    bundle_path=bundle_choice.path,
                    settings=settings,
                )
            except Exception as exc:
                console.print(f"[red]Oracle capture failed:[/red] {exc}")
                if not continue_after_capture_failure:
                    raise typer.Exit(code=1) from exc
                console.print("[yellow]Continuing with Chrome launch only.[/yellow]")
            else:
                console.print(
                    f"[green]Oracle capture saved[/green] → {oracle_path.as_posix()}",
                )

    if mode in _VIEW_COMBAT_MODES:
        console.print(
            "[dim]Capturing oracle combat renders (Figma ref, Flutter golden, diff)…[/dim]"
        )
        console.print(
            "[dim]Oracle capture uses `flutter test` (VM test compile). This is slow and "
            "blocking — use preview mode for fast human inspection. Capture timeout is 20 min. "
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
            console.print("[yellow]Continuing with Chrome launch only.[/yellow]")
            combat_flutter_ok = False
        else:
            combat_flutter_ok = render_result.flutter_capture_ok
            if combat_flutter_ok:
                console.print(
                    f"[green]Combat capture saved[/green] → "
                    f"{render_result.render_dir.as_posix()}/capture.png",
                )
                if render_result.changed_ratio is not None:
                    console.print(
                        f"[dim]Pixel diff:[/dim] {render_result.changed_ratio:.2%} changed vs Figma",
                    )
            else:
                console.print("[red]Combat capture failed[/red]")
            for warning in render_result.warnings:
                console.print(f"[yellow]{warning}[/yellow]")
            if not combat_flutter_ok and mode == "renders":
                raise typer.Exit(code=1)
            if not combat_flutter_ok and mode == "full-renders":
                console.print("[yellow]Continuing with Chrome launch only.[/yellow]")

    if mode not in _VIEW_CHROME_MODES:
        return

    device_id = resolve_flutter_device_id_from_settings(settings)
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

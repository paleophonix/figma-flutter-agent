"""Session and wizard state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer


@dataclass
class CliSession:
    """Interactive CLI session flags stored on ``typer.Context.obj``."""

    interactive: bool
    force_non_interactive: bool = False


@dataclass
class WizardState:
    """Cached wizard selections between menu iterations."""

    workspace_root: Path | None = None
    project_dir: Path | None = None
    active_screen: str | None = None


def _wizard_active_screen_label(ctx: typer.Context) -> str | None:
    """Return the session or wired active screen slug, if known."""
    from figma_flutter_agent.dev.run import detect_wired_screen_feature

    state = _wizard_state(ctx)
    if state.active_screen:
        return state.active_screen
    if state.project_dir is not None:
        return detect_wired_screen_feature(state.project_dir)
    return None


def _wizard_state(ctx: typer.Context) -> WizardState:
    if not isinstance(ctx.obj, dict):
        ctx.ensure_object(dict)
    state = ctx.obj.get("wizard")
    if not isinstance(state, WizardState):
        state = WizardState()
        ctx.obj["wizard"] = state
    return state


def _load_persisted_active_screen(project_dir: Path) -> str | None:
    """Return the active screen slug from disk prefs, if any."""
    from figma_flutter_agent.dev.wizard_prefs import load_wizard_prefs

    return load_wizard_prefs(project_dir).active_screen


def _persist_active_screen(ctx: typer.Context, screen: str | None) -> None:
    """Remember the active screen in session memory and on disk."""
    from figma_flutter_agent.dev.wizard_prefs import save_wizard_prefs

    state = _wizard_state(ctx)
    state.active_screen = screen
    if state.project_dir is not None:
        save_wizard_prefs(state.project_dir, active_screen=screen)


def _wizard_workspace_root(ctx: typer.Context) -> Path | None:
    """Return the configured workspace root (``FIGMA_FLUTTER_PROJECT_DIR``)."""
    from figma_flutter_agent.dev.project import env_configured_workspace_root

    state = _wizard_state(ctx)
    if state.workspace_root is not None:
        return state.workspace_root
    workspace = env_configured_workspace_root()
    if workspace is not None:
        state.workspace_root = workspace.resolve()
    return state.workspace_root


def _persist_active_flutter_project(
    ctx: typer.Context,
    project_dir: Path,
    *,
    workspace_root: Path | None = None,
) -> None:
    """Remember the active Flutter project in session and workspace prefs."""
    from rich.console import Console

    from figma_flutter_agent.dev.project import (
        active_project_relative_path,
        is_flutter_project_root,
    )
    from figma_flutter_agent.dev.wizard_prefs import save_workspace_prefs

    console = Console()
    state = _wizard_state(ctx)
    resolved = project_dir.expanduser().resolve()
    if not is_flutter_project_root(resolved):
        return
    state.project_dir = resolved
    workspace = workspace_root or _wizard_workspace_root(ctx)
    if workspace is not None and not is_flutter_project_root(workspace):
        save_workspace_prefs(
            workspace,
            active_project=active_project_relative_path(workspace, resolved),
        )
    from figma_flutter_agent.dev.project import ensure_batch_manifest

    created_before = (resolved / "screens.yaml").is_file()
    manifest_path = ensure_batch_manifest(resolved, workspace_root=workspace)
    if not created_before and manifest_path.is_file():
        console.print(
            f"[green]Created[/green] {manifest_path.as_posix()} "
            "(empty — use fetch or batch dump-file to add screens)"
        )


def _bootstrap_wizard_state(ctx: typer.Context) -> None:
    """Load default project and persisted active screen before the first menu draw."""
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.project import (
        env_configured_workspace_root,
        is_flutter_project_root,
        resolve_active_flutter_project,
    )
    from figma_flutter_agent.tools.stale_process_cleanup import cleanup_stale_agent_processes

    if load_settings().agent.runtime.cleanup_stale_processes_on_start:
        cleanup_stale_agent_processes()

    state = _wizard_state(ctx)
    workspace = env_configured_workspace_root()
    if workspace is not None:
        state.workspace_root = workspace.resolve()

    if state.project_dir is None or not is_flutter_project_root(state.project_dir):
        resolved = resolve_active_flutter_project(env_workspace=state.workspace_root)
        if resolved is not None:
            _persist_active_flutter_project(ctx, resolved, workspace_root=state.workspace_root)
    if state.project_dir is not None and state.active_screen is None:
        state.active_screen = _load_persisted_active_screen(state.project_dir)


def _wizard_project_dir(ctx: typer.Context) -> Path:
    from figma_flutter_agent.dev.project import (
        default_flutter_project_candidate,
        discover_flutter_projects,
        env_configured_workspace_root,
        is_flutter_project_root,
        resolve_active_flutter_project,
    )
    from figma_flutter_agent.errors import FlutterProjectError
    from figma_flutter_agent.wizard.prompts import prompt_project_dir

    state = _wizard_state(ctx)
    if state.project_dir is not None and is_flutter_project_root(state.project_dir):
        return state.project_dir

    workspace = _wizard_workspace_root(ctx) or env_configured_workspace_root()
    resolved = resolve_active_flutter_project(env_workspace=workspace)
    if resolved is not None:
        _persist_active_flutter_project(ctx, resolved, workspace_root=workspace)
        if state.active_screen is None:
            state.active_screen = _load_persisted_active_screen(state.project_dir)
        return state.project_dir

    if workspace is not None and workspace.is_dir():
        projects = discover_flutter_projects(workspace)
        if len(projects) > 1:
            raise FlutterProjectError(
                "Multiple Flutter projects under FIGMA_FLUTTER_PROJECT_DIR — "
                "run switch (menu option 1) to choose the active project."
            )

    state.project_dir = prompt_project_dir(
        ctx,
        default_flutter_project_candidate(env_project_dir=workspace),
        env_project_dir=workspace,
    )
    _persist_active_flutter_project(ctx, state.project_dir, workspace_root=workspace)
    if state.active_screen is None:
        state.active_screen = _load_persisted_active_screen(state.project_dir)
    return state.project_dir

"""Menu option lists and header rendering."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()

_MENU_RETURN_OPTION = "return — back to main menu"


def _with_main_menu_return(options: list[str]) -> list[str]:
    """Append the standard back navigation item for first-level wizard submenus."""
    if options and options[-1].startswith("return —"):
        return list(options)
    return [*options, _MENU_RETURN_OPTION]


def _is_menu_return(option: str) -> bool:
    """Return True when the user picked the submenu return item."""
    return option.partition(" — ")[0] == "return"


def _wizard_menu_options() -> list[str]:
    """Menu items: quick launch first, then setup → fetch → generate → validate."""
    return [
        "launch — cached dump + screen IR, flutter run (no LLM)",
        "switch — change active Flutter project",
        "check — fonts, assets, doctor, live Figma connectivity",
        "fetch — import frame or dump file from Figma",
        "list — view manifest and preflight status",
        "select — pick active screen",
        "generate — codegen one or all screens",
        "run — generate, sync, and launch Flutter",
        "debug — OpenCode repair on .debug artifacts (no generate)",
        "view — launch Chrome or capture PNG / combat renders",
    ]


def _check_menu_options() -> list[str]:
    """Sub-menu for environment and connectivity checks."""
    return _with_main_menu_return(
        [
            "all — fonts + assets + doctor + live Figma check",
            "all-fonts — audit assets/fonts/ on disk",
            "screen-fonts — design fonts for active screen dump",
            "all-assets — audit assets/icons|images|illustrations on disk",
            "screen-assets — exportable icons for active screen dump",
            "doctor — Figma token, Flutter SDK, project files",
            "live-check — verify Figma token and API fetch",
            "analyze — run flutter analyze on project",
        ]
    )


def _generate_menu_options() -> list[str]:
    """Sub-menu for single-screen vs batch codegen."""
    return _with_main_menu_return(
        [
            "batch — codegen all screens from screens.yaml",
            "one — codegen one Figma frame",
        ]
    )


def _run_menu_options() -> list[str]:
    """Sub-menu for generate/assets/sync before Flutter launch."""
    return _with_main_menu_return(
        [
            "ir-offline — cached dump + .debug/ir, flutter run (no LLM)",
            "full — generate, sync assets, flutter run",
            "offline — generate from cache, flutter run (no live assets)",
        ]
    )


def _import_manifest_menu_options() -> list[str]:
    """Sub-menu for merging or replacing ``screens.yaml`` during fetch."""
    return [
        "add — merge into existing screens.yaml",
        "overwrite — replace screens.yaml with this import",
    ]


def _list_menu_options() -> list[str]:
    """Sub-menu for manifest listing, rename, and screen removal."""
    return _with_main_menu_return(
        [
            "view — show manifest and preflight status",
            "rename — change a screen slug in screens.yaml",
            "assets — export SVG/PNG from cached dump (Figma Images API)",
            "delete — remove screens and purge lib/assets/debug (numbers or slugs)",
            "copy — copy screen(s) to another Flutter project",
        ]
    )


def _file_fetch_menu_options() -> list[str]:
    """Sub-menu for full-file fetch scope in the interactive wizard."""
    return _with_main_menu_return(
        [
            "quick — JSON + SVG + PNG, rewrite all",
            "advanced — choose scope and write policy",
        ]
    )


def _frame_fetch_menu_options() -> list[str]:
    """Sub-menu for single-frame fetch scope (first level under ``fetch``)."""
    from figma_flutter_agent.batch.dump_mode import frame_fetch_menu_options

    return _with_main_menu_return(frame_fetch_menu_options())


def _debug_menu_options() -> list[str]:
    """Sub-menu for OpenCode repair: new case, resume, or flutter run from worktree."""
    return _with_main_menu_return(
        [
            "new — start new repair worktree",
            "continue — resume repair on existing worktree",
            "run — launch Flutter from worktree debug bundle",
        ]
    )


def _view_menu_options() -> list[str]:
    """Sub-menu for wizard view: PNG capture, combat renders, and Chrome launch combos."""
    return _with_main_menu_return(
        [
            "chrome — launch lib/ screen in Chrome (no capture)",
            "preview — capture PNG only (oracle when configured)",
            "renders — Figma ref + Flutter golden + diff heatmap",
            "full-review — capture PNG then launch Chrome",
            "full-renders — combat renders then launch Chrome",
        ]
    )


def _resolve_run_prefer_live(
    *,
    prefer_live: bool | None,
    has_token: bool,
) -> bool | None:
    """Map run/launch mode to live Figma sync vs cached dump.

    ``prefer_live`` True forces live sync when a token exists; False forces the
    cached dump; None lets :func:`resolve_live_sync` decide from preflight.
    """
    if prefer_live is None:
        return None
    if prefer_live:
        return has_token
    return False


def _print_wizard_header(ctx: typer.Context) -> None:
    from figma_flutter_agent.dev.project import is_flutter_project_root
    from figma_flutter_agent.wizard.state import (
        _wizard_active_screen_label,
        _wizard_state,
        _wizard_workspace_root,
    )

    state = _wizard_state(ctx)
    console.print("figma-flutter — interactive mode")
    workspace = _wizard_workspace_root(ctx)
    if workspace is not None and not is_flutter_project_root(workspace):
        console.print(f"Workspace: {workspace.as_posix()}")
    if state.project_dir is not None:
        active = _wizard_active_screen_label(ctx)
        active_label = active if active is not None else "not set"
        console.print(f"Project: {state.project_dir.as_posix()}  Active screen: {active_label}")
    elif workspace is not None:
        console.print("Project: not set — use switch to pick a Flutter app")
    console.print("")


def _wizard_pick_flutter_device(*, flutter_sdk: str | None = None) -> str | None:
    """Deprecated: configure ``runtime.flutter_device_id`` in ``.ai-figma-flutter.yml`` instead."""
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.wizard.devices import resolve_flutter_device_id

    settings = load_settings()
    return resolve_flutter_device_id(
        flutter_sdk=flutter_sdk or settings.flutter_sdk or None,
        configured=settings.agent.runtime.flutter_device_id,
    )


def _default_chrome_device_id(*, flutter_sdk: str | None) -> str | None:
    """Deprecated: use :func:`resolve_flutter_device_id` with YAML ``runtime.flutter_device_id``."""
    from figma_flutter_agent.dev.wizard.devices import resolve_flutter_device_id

    return resolve_flutter_device_id(flutter_sdk=flutter_sdk, configured=None)


def _prompt_view_bundle_choice(
    project_dir: Path,
    feature_name: str,
):
    """Prompt for an on-disk debug bundle; ``ref`` selects ``.debug/reference``."""
    from figma_flutter_agent.dev.debug_view import (
        discover_view_bundle_choices,
        resolve_view_bundle_choice_input,
    )
    from figma_flutter_agent.errors import FlutterProjectError
    from figma_flutter_agent.wizard.prompts import _colorize_choice_label

    choices = discover_view_bundle_choices(project_dir, feature_name)
    if not choices:
        raise FlutterProjectError(
            f"No debug bundles for {feature_name!r} under {project_dir.as_posix()}/.debug. "
            "Run generate first (dart) or write_emitter_reference (ref)."
        )

    labels = [choice.menu_label for choice in choices]
    default_index = 0
    for index, choice in enumerate(choices):
        if choice.source.value == "reference":
            default_index = index
            break

    console.print("[bold]Bundle source[/bold]")
    console.print(
        f"[dim]Keys: dart (final), ref / reference (golden), plan — or enter 1-{len(choices)}[/dim]"
    )
    for index, label in enumerate(labels):
        display = index + 1
        marker = " [cyan](default)[/cyan]" if index == default_index else ""
        console.print(f"  {display}. {_colorize_choice_label(label)}{marker}")

    import typer as _typer

    default_display = default_index + 1
    while True:
        raw = _typer.prompt("Choice", default=str(default_display)).strip()
        picked = resolve_view_bundle_choice_input(raw, choices)
        if picked is not None:
            return choices[picked]
        from figma_flutter_agent.wizard.prompts import _menu_command

        for choice in choices:
            if raw == choice.menu_label or raw == _menu_command(choice.menu_label):
                return choice
        console.print(
            f"[red]Invalid choice — enter 1-{len(choices)}, dart, ref, reference, or plan.[/red]"
        )


def _prompt_import_manifest_mode(manifest_path: Path) -> bool:
    """Return True when the import should merge into an existing manifest."""
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice

    if not manifest_path.is_file():
        return True
    from figma_flutter_agent.batch.manifest import load_batch_manifest

    manifest = load_batch_manifest(manifest_path)
    if not manifest.screens:
        return True
    mode_label = prompt_choice(
        "Import into screens.yaml",
        _import_manifest_menu_options(),
        default=_import_manifest_menu_options()[0],
    )
    return _menu_command(mode_label) == "add"

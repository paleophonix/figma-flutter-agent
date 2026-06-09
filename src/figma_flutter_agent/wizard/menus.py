"""Menu option lists and header rendering."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()


def _wizard_menu_options() -> list[str]:
    """Menu items: quick launch first, then setup → fetch → generate → validate."""
    return [
        "launch — cached dump + screen IR, flutter run (no LLM)",
        "switch — change active Flutter project",
        "check — fonts, doctor, live Figma connectivity",
        "fetch — import frame or dump file from Figma",
        "list — view manifest and preflight status",
        "select — pick active screen",
        "generate — codegen one or all screens",
        "run — generate, sync, and launch Flutter",
        "analyze — run flutter analyze on project",
        "view — preview bundle or combat renders (ref/golden/diff)",
    ]


def _check_menu_options() -> list[str]:
    """Sub-menu for environment and connectivity checks."""
    return [
        "all — fonts + doctor + live Figma check",
        "fonts — audit assets/fonts/ and active screen dump",
        "doctor — Figma token, Flutter SDK, project files",
        "live-check — verify Figma token and API fetch",
    ]


def _generate_menu_options() -> list[str]:
    """Sub-menu for single-screen vs batch codegen."""
    return [
        "batch — codegen all screens from screens.yaml",
        "one — codegen one Figma frame",
    ]


def _run_menu_options() -> list[str]:
    """Sub-menu for generate/assets/sync before Flutter launch."""
    return [
        "ir-offline — cached dump + .figma_debug/ir, flutter run (no LLM)",
        "full — generate, sync assets, flutter run",
        "offline — generate from cache, flutter run (no live assets)",
    ]


def _import_manifest_menu_options() -> list[str]:
    """Sub-menu for merging or replacing ``screens.yaml`` during fetch."""
    return [
        "add — merge into existing screens.yaml",
        "overwrite — replace screens.yaml with this import",
    ]


def _list_menu_options() -> list[str]:
    """Sub-menu for manifest listing, rename, and screen removal."""
    return [
        "view — show manifest and preflight status",
        "rename — change a screen slug in screens.yaml",
        "assets — export SVG/PNG from cached dump (Figma Images API)",
        "delete — remove screens (comma-separated slugs)",
    ]


def _file_fetch_menu_options() -> list[str]:
    """Sub-menu for full-file fetch scope in the interactive wizard."""
    return [
        "quick — JSON + SVG + PNG, rewrite all",
        "advanced — choose scope and write policy",
    ]


def _view_menu_options() -> list[str]:
    """Sub-menu for wizard view: Chrome preview vs combat PNG captures."""
    return [
        "preview — deploy bundle and launch Chrome",
        "renders — Figma ref + Flutter golden + diff → logs/renders",
        "full — combat renders then preview",
    ]


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
    """Prompt for a Flutter run target or return None for the default device."""
    from figma_flutter_agent.config import load_settings
    from figma_flutter_agent.dev.wizard import (
        default_flutter_device_option,
        device_id_from_choice,
        list_flutter_devices,
    )
    from figma_flutter_agent.wizard.prompts import prompt_choice

    sdk = flutter_sdk or load_settings().flutter_sdk or None
    devices = list_flutter_devices(flutter_sdk=sdk)
    if not devices:
        console.print("[yellow]No flutter devices listed — Flutter will pick a default.[/yellow]")
        return None
    options = [f"{label} [{device_id}]" for device_id, label in devices]
    options.append("default — let Flutter choose")
    picked = prompt_choice(
        "Flutter device",
        options,
        default=default_flutter_device_option(devices) or options[0],
    )
    if picked.startswith("default"):
        return None
    return device_id_from_choice(picked)


def _default_chrome_device_id(*, flutter_sdk: str | None) -> str | None:
    """Resolve Chrome (web-javascript) for one-tap launch, or None when unavailable."""
    from figma_flutter_agent.dev.wizard import (
        default_flutter_device_option,
        device_id_from_choice,
        list_flutter_devices,
    )

    devices = list_flutter_devices(flutter_sdk=flutter_sdk)
    option = default_flutter_device_option(devices)
    if option is None:
        return None
    return device_id_from_choice(option)


def _prompt_view_bundle_choice(
    project_dir: Path,
    feature_name: str,
):
    """Prompt for an on-disk debug bundle; ``ref`` selects ``.figma_debug/reference``."""
    from figma_flutter_agent.dev.debug_view import (
        discover_view_bundle_choices,
        resolve_view_bundle_choice_input,
    )
    from figma_flutter_agent.errors import FlutterProjectError
    from figma_flutter_agent.wizard.prompts import _colorize_choice_label

    choices = discover_view_bundle_choices(project_dir, feature_name)
    if not choices:
        raise FlutterProjectError(
            f"No debug bundles for {feature_name!r} under {project_dir.as_posix()}/.figma_debug. "
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
        "[dim]Keys: dart (final), ref / reference (golden), plan — or enter 1-"
        f"{len(choices)}[/dim]"
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

        for index, choice in enumerate(choices):
            if raw == choice.menu_label or raw == _menu_command(choice.menu_label):
                return choice
        console.print(
            "[red]Invalid choice — enter 1-"
            f"{len(choices)}, dart, ref, reference, or plan.[/red]"
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

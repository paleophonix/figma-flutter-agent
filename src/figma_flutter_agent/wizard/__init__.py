"""Interactive CLI wizard package — main entry and public re-exports."""

from __future__ import annotations

import typer
from rich.console import Console

from figma_flutter_agent.wizard.check import (
    _wizard_check,
    _wizard_doctor,
    _wizard_flutter_analyze,
    _wizard_live_check,
    _wizard_print_font_audit,
)
from figma_flutter_agent.wizard.debug import (
    _wizard_agent_signoff,
    _wizard_debug_view,
)
from figma_flutter_agent.wizard.debug_agent import _wizard_debug
from figma_flutter_agent.wizard.fetch import (
    _wizard_dump_figma_file,
    _wizard_fetch_from_figma,
    _wizard_import_figma_frame,
)
from figma_flutter_agent.wizard.generate import (
    _wizard_batch_generate,
    _wizard_generate,
    _wizard_generate_menu,
)
from figma_flutter_agent.wizard.menus import (
    _check_menu_options,
    _default_chrome_device_id,
    _file_fetch_menu_options,
    _frame_fetch_menu_options,
    _generate_menu_options,
    _import_manifest_menu_options,
    _is_menu_return,
    _list_menu_options,
    _print_wizard_header,
    _prompt_import_manifest_mode,
    _prompt_view_bundle_choice,
    _resolve_run_prefer_live,
    _run_menu_options,
    _view_menu_options,
    _wizard_menu_options,
    _wizard_pick_flutter_device,
)
from figma_flutter_agent.wizard.prompts import (
    _choice_display_index,
    _choice_index_from_input,
    _choice_label_style,
    _colorize_choice_label,
    _menu_command,
    _prompting_enabled,
    _wizard_default_figma_input,
    ensure_llm_generation_ready,
    get_session,
    is_interactive,
    print_pipeline_warnings,
    prompt_choice,
    prompt_confirm,
    prompt_figma_file_key,
    prompt_figma_frame_url,
    prompt_figma_input,
    prompt_import_feature_name,
    prompt_manifest_path,
    prompt_project_dir,
    prompt_screen_name,
    prompt_text,
    should_prompt,
    tty_interactive_default,
)
from figma_flutter_agent.wizard.run_actions import (
    _wizard_launch_defaults,
    _wizard_run,
    _wizard_sync_preview,
)
from figma_flutter_agent.wizard.screens import (
    _wizard_delete_screens,
    _wizard_export_screen_assets,
    _wizard_list_screens,
    _wizard_list_screens_view,
    _wizard_pick_screen,
    _wizard_rename_screen,
    _wizard_resolve_active_dump,
    _wizard_resolve_screen,
    _wizard_select_active_screen,
    _wizard_switch_project,
)
from figma_flutter_agent.wizard.state import (
    CliSession,
    WizardState,
    _bootstrap_wizard_state,
    _load_persisted_active_screen,
    _persist_active_flutter_project,
    _persist_active_screen,
    _wizard_active_screen_label,
    _wizard_project_dir,
    _wizard_state,
    _wizard_workspace_root,
)

console = Console()


def run_main_wizard(ctx: typer.Context) -> None:
    """Top-level interactive menu when ``figma-flutter`` is invoked without a subcommand."""
    from figma_flutter_agent.errors import FigmaFlutterError, format_error_for_log

    _bootstrap_wizard_state(ctx)
    _print_wizard_header(ctx)
    while True:
        action = prompt_choice(
            "What would you like to do?",
            _wizard_menu_options(),
            default=_wizard_menu_options()[0],
            zero_indexed=True,
        )
        command = _menu_command(action)
        try:
            if command == "switch":
                _wizard_switch_project(ctx)
            elif command == "launch":
                _wizard_launch_defaults(ctx)
            elif command == "check":
                _wizard_check(ctx)
            elif command == "fetch":
                _wizard_fetch_from_figma(ctx)
            elif command == "list":
                _wizard_list_screens(ctx)
            elif command == "select":
                _wizard_select_active_screen(ctx)
            elif command == "generate":
                _wizard_generate_menu(ctx)
            elif command == "run":
                _wizard_run(ctx)
            elif command == "debug":
                _wizard_debug(ctx)
            elif command == "view":
                _wizard_debug_view(ctx)
            else:
                console.print(f"[yellow]Unknown action:[/yellow] {action}")
        except typer.Exit as exc:
            if exc.exit_code:
                console.print("[red]Action failed.[/red]")
            else:
                raise
        except FigmaFlutterError as exc:
            console.print(f"[red]Error:[/red] {format_error_for_log(exc)}")
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            console.print(f"[red]Error:[/red] {format_error_for_log(exc)}")
        console.print("")
        _print_wizard_header(ctx)


__all__ = [
    "run_main_wizard",
    # prompts
    "print_pipeline_warnings",
    "tty_interactive_default",
    "get_session",
    "is_interactive",
    "should_prompt",
    "prompt_text",
    "prompt_confirm",
    "_colorize_choice_label",
    "_choice_label_style",
    "_menu_command",
    "_choice_display_index",
    "_choice_index_from_input",
    "prompt_choice",
    "ensure_llm_generation_ready",
    "_prompting_enabled",
    "prompt_project_dir",
    "prompt_import_feature_name",
    "prompt_screen_name",
    "prompt_figma_file_key",
    "prompt_figma_frame_url",
    "_wizard_default_figma_input",
    "prompt_figma_input",
    "prompt_manifest_path",
    # state
    "CliSession",
    "WizardState",
    "_wizard_active_screen_label",
    "_wizard_state",
    "_load_persisted_active_screen",
    "_persist_active_screen",
    "_wizard_workspace_root",
    "_persist_active_flutter_project",
    "_bootstrap_wizard_state",
    "_wizard_project_dir",
    # menus
    "_wizard_menu_options",
    "_check_menu_options",
    "_generate_menu_options",
    "_run_menu_options",
    "_import_manifest_menu_options",
    "_list_menu_options",
    "_file_fetch_menu_options",
    "_frame_fetch_menu_options",
    "_is_menu_return",
    "_view_menu_options",
    "_prompt_view_bundle_choice",
    "_print_wizard_header",
    "_wizard_pick_flutter_device",
    "_default_chrome_device_id",
    "_resolve_run_prefer_live",
    "_prompt_import_manifest_mode",
    # actions
    "_wizard_resolve_screen",
    "_wizard_resolve_active_dump",
    "_wizard_print_font_audit",
    "_wizard_check",
    "_wizard_generate_menu",
    "_wizard_run",
    "_wizard_launch_defaults",
    "_wizard_sync_preview",
    "_wizard_doctor",
    "_wizard_flutter_analyze",
    "_wizard_debug",
    "_wizard_debug_view",
    "_wizard_agent_signoff",
    "_wizard_switch_project",
    "_wizard_select_active_screen",
    "_wizard_pick_screen",
    "_wizard_generate",
    "_wizard_fetch_from_figma",
    "_wizard_import_figma_frame",
    "_wizard_dump_figma_file",
    "_wizard_rename_screen",
    "_wizard_export_screen_assets",
    "_wizard_batch_generate",
    "_wizard_list_screens",
    "_wizard_list_screens_view",
    "_wizard_delete_screens",
    "_wizard_live_check",
]

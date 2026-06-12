"""Tests for interactive menu rendering."""

from __future__ import annotations

from figma_flutter_agent.wizard import (
    _check_menu_options,
    _colorize_choice_label,
    _file_fetch_menu_options,
    _generate_menu_options,
    _is_menu_return,
    _menu_command,
    _resolve_run_prefer_live,
    _run_menu_options,
    _wizard_menu_options,
)


def test_colorize_choice_label_yellow_command_prefix() -> None:
    rendered = _colorize_choice_label("check — doctor and/or live Figma connectivity")
    assert "[bold yellow]check[/bold yellow]" in rendered
    assert "doctor and/or live Figma connectivity" in rendered


def test_colorize_choice_label_yellow_submenu_items() -> None:
    rendered = _colorize_choice_label("batch — codegen all screens from screens.yaml")
    assert "[bold yellow]batch[/bold yellow]" in rendered


def test_colorize_choice_label_colors_launch_red() -> None:
    rendered = _colorize_choice_label(
        "launch — cached dump + screen IR, flutter run (no LLM)"
    )
    assert "[bold red]launch[/bold red]" in rendered


def test_menu_command_extracts_prefix() -> None:
    assert _menu_command("run — generate, sync, and launch Flutter") == "run"
    assert (
        _menu_command("launch — cached dump + screen IR, flutter run (no LLM)")
        == "launch"
    )


def test_wizard_menu_uses_short_labels() -> None:
    options = _wizard_menu_options()
    commands = [_menu_command(option) for option in options]
    assert commands == [
        "launch",
        "switch",
        "check",
        "fetch",
        "list",
        "select",
        "generate",
        "run",
        "analyze",
        "view",
    ]
    assert options[0].startswith("launch —")


def test_wizard_menu_has_single_fetch_entry() -> None:
    options = _wizard_menu_options()
    fetch_items = [option for option in options if _menu_command(option) == "fetch"]
    assert len(fetch_items) == 1
    assert "import frame or dump file" in fetch_items[0]
    assert "import from Figma URL" not in "\n".join(options)
    assert "batch dump-file" not in "\n".join(options)
    assert "doctor —" not in "\n".join(options)
    assert "live-check —" not in "\n".join(options)
    assert "batch generate" not in "\n".join(options)
    assert "sync & preview" not in "\n".join(options)
    assert "agent sign-off" not in "\n".join(options)


def test_check_submenu_defaults_to_all() -> None:
    options = _check_menu_options()
    assert options[0].startswith("all —")
    assert any("fonts —" in option for option in options)
    assert _menu_command(options[-1]) == "return"


def test_generate_submenu_defaults_to_batch() -> None:
    options = _generate_menu_options()
    assert options[0].startswith("batch —")
    assert any(option.startswith("one —") for option in options)


def test_run_submenu_defaults_to_ir_offline() -> None:
    options = _run_menu_options()
    commands = [_menu_command(option) for option in options]
    assert commands == ["ir-offline", "full", "offline", "return"]
    assert options[0].startswith("ir-offline —")
    assert options[-1].startswith("return —")


def test_resolve_run_prefer_live_full_uses_live_when_token_configured() -> None:
    assert _resolve_run_prefer_live(prefer_live=True, has_token=True) is True


def test_resolve_run_prefer_live_full_falls_back_to_cache_without_token() -> None:
    assert _resolve_run_prefer_live(prefer_live=True, has_token=False) is False


def test_resolve_run_prefer_live_offline_always_uses_cache() -> None:
    assert _resolve_run_prefer_live(prefer_live=False, has_token=True) is False
    assert _resolve_run_prefer_live(prefer_live=False, has_token=False) is False


def test_resolve_run_prefer_live_smart_mode_defers_to_preflight() -> None:
    assert _resolve_run_prefer_live(prefer_live=None, has_token=True) is None
    assert _resolve_run_prefer_live(prefer_live=None, has_token=False) is None


def test_file_fetch_submenu_has_quick_and_advanced() -> None:
    options = _file_fetch_menu_options()
    assert options[0].startswith("quick")
    assert options[1].startswith("advanced")
    assert _menu_command(options[-1]) == "return"


def test_first_level_submenus_end_with_return() -> None:
    for options_fn in (_check_menu_options, _generate_menu_options, _run_menu_options):
        options = options_fn()
        assert _menu_command(options[-1]) == "return"
    assert _is_menu_return("return — back to main menu")


def test_colorize_fetch_label() -> None:
    rendered = _colorize_choice_label(
        "fetch — import frame or dump file from Figma"
    )
    assert "[bold yellow]fetch[/bold yellow]" in rendered

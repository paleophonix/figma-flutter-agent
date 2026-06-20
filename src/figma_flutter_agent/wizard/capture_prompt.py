"""Wizard golden-capture prompt shared by generate and run menus."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from figma_flutter_agent.config import Settings, load_settings

console = Console()


def capture_prompt_options() -> list[str]:
    """Menu labels for post-codegen golden capture."""
    return [
        "with — golden capture after codegen (flutter_render + capture.json)",
        "without — skip capture (faster)",
    ]


def apply_wizard_debug_capture(settings: Settings, *, enabled: bool) -> Settings:
    """Return settings with ``dev.debug_capture`` overridden for one wizard run."""
    agent = settings.agent.model_copy(deep=True)
    dev = agent.dev.model_copy(update={"debug_capture": enabled})
    return settings.model_copy(update={"agent": agent.model_copy(update={"dev": dev})})


def prompt_wizard_capture_settings(config_path: Path) -> Settings:
    """Load settings and ask whether to run post-codegen golden capture."""
    from figma_flutter_agent.wizard.prompts import _menu_command, prompt_choice

    settings = load_settings(config_path)
    yaml_default = settings.agent.dev.debug_capture
    options = capture_prompt_options()
    default_label = options[0] if yaml_default else options[1]
    choice = prompt_choice(
        "Golden capture",
        options,
        default=default_label,
    )
    with_capture = _menu_command(choice) == "with"
    if with_capture != yaml_default:
        console.print(
            "[dim]Capture override:[/dim] "
            f"{'on' if with_capture else 'off'} "
            f"(yaml dev.debug_capture={yaml_default})"
        )
    return apply_wizard_debug_capture(settings, enabled=with_capture)

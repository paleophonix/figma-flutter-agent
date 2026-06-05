"""Interactive and CLI generation layout mode selection."""

from __future__ import annotations

from enum import StrEnum

from figma_flutter_agent.config import Settings


class GenerationLayoutMode(StrEnum):
    """Screen body codegen backend."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"


_GENERATION_MENU: tuple[tuple[str, GenerationLayoutMode], ...] = (
    ("llm — LLM screen body (needs LLM API key in .env)", GenerationLayoutMode.LLM),
    ("deterministic — rule-based layout (no LLM key)", GenerationLayoutMode.DETERMINISTIC),
)


def generation_mode_menu_options() -> list[str]:
    """Return menu labels for deterministic vs LLM generation."""
    return [label for label, _mode in _GENERATION_MENU]


def generation_mode_from_menu(label: str) -> GenerationLayoutMode:
    """Map an interactive menu label to ``GenerationLayoutMode``."""
    for option_label, mode in _GENERATION_MENU:
        if label == option_label:
            return mode
    msg = f"Unknown generation mode menu option: {label!r}"
    raise ValueError(msg)


def generation_mode_menu_label(mode: GenerationLayoutMode) -> str:
    """Return the interactive menu label for ``mode``."""
    for option_label, menu_mode in _GENERATION_MENU:
        if menu_mode is mode:
            return option_label
    msg = f"Unknown generation layout mode: {mode!r}"
    raise ValueError(msg)


def wizard_default_generation_layout_mode() -> GenerationLayoutMode:
    """Return the generation mode pre-selected in the interactive wizard."""
    return GenerationLayoutMode.LLM


def default_generation_layout_mode(settings: Settings) -> GenerationLayoutMode:
    """Return the mode implied by project YAML defaults."""
    if settings.agent.generation.use_deterministic_screen:
        return GenerationLayoutMode.DETERMINISTIC
    return GenerationLayoutMode.LLM


def apply_generation_layout_mode(
    settings: Settings,
    mode: GenerationLayoutMode,
) -> Settings:
    """Override generation mode for one pipeline run.

    Explicit LLM selection disables silent deterministic fallback so LLM failures
    surface instead of producing a layout-delegate screen identical to deterministic
    output.
    """
    updated = settings.with_deterministic_screen(
        use_deterministic_screen=mode is GenerationLayoutMode.DETERMINISTIC,
    )
    if mode is GenerationLayoutMode.LLM:
        return updated.with_llm_fallback_to_deterministic(llm_fallback_to_deterministic=False)
    return updated


def generation_mode_run_label(mode: GenerationLayoutMode) -> str:
    """Return a short human-readable label for logs and the interactive wizard."""
    if mode is GenerationLayoutMode.LLM:
        return "LLM screen body (fail-fast, no deterministic fallback)"
    return "deterministic rule-based layout"


def force_llm_regen_for_mode(mode: GenerationLayoutMode) -> bool:
    """Return whether an explicit interactive mode choice should refresh LLM output."""
    return mode is GenerationLayoutMode.LLM


def resolve_generation_layout_mode(
    settings: Settings,
    *,
    mode: GenerationLayoutMode | None,
) -> GenerationLayoutMode:
    """Resolve explicit CLI mode or fall back to YAML defaults."""
    if mode is not None:
        return mode
    return default_generation_layout_mode(settings)


def resolve_generation_settings(
    settings: Settings,
    *,
    mode: GenerationLayoutMode | None,
) -> tuple[Settings, GenerationLayoutMode]:
    """Apply an explicit or YAML-default generation layout mode."""
    resolved = resolve_generation_layout_mode(settings, mode=mode)
    return apply_generation_layout_mode(settings, resolved), resolved

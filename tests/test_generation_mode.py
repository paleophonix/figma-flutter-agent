"""Tests for deterministic vs LLM generation mode selection."""

from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings
from figma_flutter_agent.generation.mode import (
    GenerationLayoutMode,
    apply_generation_layout_mode,
    default_generation_layout_mode,
    force_llm_regen_for_mode,
    generation_mode_menu_label,
    resolve_generation_settings,
    wizard_default_generation_layout_mode,
)


def _settings(*, deterministic: bool) -> Settings:
    return Settings(
        agent=AgentYamlConfig(
            generation=GenerationConfig(use_deterministic_screen=deterministic),
        )
    )


def test_default_generation_layout_mode_from_yaml() -> None:
    assert default_generation_layout_mode(_settings(deterministic=True)) is (
        GenerationLayoutMode.DETERMINISTIC
    )
    assert (
        default_generation_layout_mode(_settings(deterministic=False)) is GenerationLayoutMode.LLM
    )


def test_wizard_default_generation_layout_mode_is_llm() -> None:
    from figma_flutter_agent.generation.mode import generation_mode_menu_options

    assert wizard_default_generation_layout_mode() is GenerationLayoutMode.LLM
    assert generation_mode_menu_label(GenerationLayoutMode.LLM).startswith("llm")
    options = generation_mode_menu_options()
    assert options[0].startswith("llm")
    assert options[1].startswith("deterministic")


def test_apply_generation_layout_mode_overrides_yaml() -> None:
    settings = _settings(deterministic=True)
    updated = apply_generation_layout_mode(settings, GenerationLayoutMode.LLM)
    assert updated.agent.generation.use_deterministic_screen is False
    assert updated.agent.generation.llm_fallback_to_deterministic is False


def test_apply_generation_layout_mode_keeps_fallback_for_deterministic() -> None:
    settings = Settings(
        agent=AgentYamlConfig(
            generation=GenerationConfig(
                use_deterministic_screen=False,
                llm_fallback_to_deterministic=True,
            ),
        )
    )
    updated = apply_generation_layout_mode(settings, GenerationLayoutMode.DETERMINISTIC)
    assert updated.agent.generation.use_deterministic_screen is True
    assert updated.agent.generation.llm_fallback_to_deterministic is True


def test_force_llm_regen_for_mode() -> None:
    assert force_llm_regen_for_mode(GenerationLayoutMode.LLM) is True
    assert force_llm_regen_for_mode(GenerationLayoutMode.DETERMINISTIC) is False


def test_resolve_generation_settings_uses_explicit_mode() -> None:
    settings = _settings(deterministic=True)
    updated, mode = resolve_generation_settings(
        settings,
        mode=GenerationLayoutMode.LLM,
    )
    assert mode is GenerationLayoutMode.LLM
    assert updated.agent.generation.use_deterministic_screen is False

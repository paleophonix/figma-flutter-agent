"""Tests for theme-aware LLM prompts."""

from figma_flutter_agent.llm.prompts import build_system_prompt


def test_build_system_prompt_cupertino_allows_cupertino_widgets() -> None:
    prompt = build_system_prompt(theme_variant="cupertino")

    assert "CupertinoButton" in prompt
    assert "do not replace native Cupertino button structures with Material tokens" in prompt
    assert "Do not generate routing" in build_system_prompt(
        routing_enabled=False,
        theme_variant="cupertino",
    )


def test_build_system_prompt_material_forbids_cupertino_controls() -> None:
    prompt = build_system_prompt(theme_variant="material_3")

    assert "Material 3" in prompt
    assert "CupertinoNavigationBar" not in prompt

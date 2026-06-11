"""Generation prompt builders."""

from __future__ import annotations

from figma_flutter_agent.llm.prompts.compose import (
    _build_l3_extensions,
    _build_l5_extensions,
    _render_generate_prompt,
)


def build_system_prompt(
    *,
    routing_enabled: bool = False,
    theme_variant: str = "material_3",
    figma_reference_attached: bool = False,
    stack_root: bool = False,
    use_screen_ir: bool = False,
) -> str:
    """Build the LLM system prompt for screen codegen.

    Composes a prebuilt generate body (Material 3 or Cupertino) with optional appendices
    for prototype routing, an attached Figma PNG, or a STACK-root layout.

    Args:
        routing_enabled: When True, append prototype ``PrototypeNavigation`` rules.
        theme_variant: ``material_3`` (default) or ``cupertino``.
        figma_reference_attached: When True, append PNG gold-standard rules.
        stack_root: When True, append absolute ``Positioned`` layout rules.
        use_screen_ir: When True, require ``screenIr`` tree output instead of ``screenCode``.

    Returns:
        System prompt string for ``generate`` LLM calls.
    """
    return _render_generate_prompt(
        theme_variant,
        l3_principles_ext=_build_l3_extensions(
            routing_enabled=routing_enabled,
            figma_reference_attached=figma_reference_attached,
        ),
        l5_actions_ext=_build_l5_extensions(
            routing_enabled=routing_enabled,
            stack_root=stack_root,
        ),
        use_screen_ir=use_screen_ir,
    )

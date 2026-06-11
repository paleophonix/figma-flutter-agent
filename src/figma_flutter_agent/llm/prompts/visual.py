"""Visual-refine prompt builders."""

from __future__ import annotations

from figma_flutter_agent.llm.prompts.compose import (
    _build_l3_extensions,
    _build_l5_extensions,
    _render_generate_prompt,
)
from figma_flutter_agent.llm.prompts.models import _REFINE_IMAGE_ROLES
from figma_flutter_agent.llm.prompts.shared import _L1_REFINE


def visual_refine_attached_images() -> list[dict[str, str | int]]:
    """Return image-role metadata embedded in visual-refine user JSON.

    Returns:
        Three descriptors (figma reference, Flutter render, diff heatmap) in display order.
    """
    return [dict(role) for role in _REFINE_IMAGE_ROLES]


def build_visual_refine_system_prompt(
    *,
    routing_enabled: bool = False,
    theme_variant: str = "material_3",
    stack_root: bool = False,
    surgical_widgets: bool = False,
    use_screen_ir: bool = False,
) -> str:
    """Build the LLM system prompt for visual refine (three PNGs + pixel diff).

    Reuses ``build_system_prompt`` with Figma PNG rules enabled, then appends refine-specific
    multimodal instructions. Optional surgical mode limits edits to snippet targets.

    Args:
        routing_enabled: Passed through to ``build_system_prompt``.
        theme_variant: ``material_3`` (default) or ``cupertino``.
        stack_root: When True, append STACK-root layout rules on the generate base.
        surgical_widgets: When True, append snippet-only edit constraints.

    Returns:
        System prompt string for ``visual_refine`` LLM calls.
    """
    return _render_generate_prompt(
        theme_variant,
        l1_purpose=_L1_REFINE,
        l3_principles_ext=_build_l3_extensions(
            routing_enabled=routing_enabled,
            figma_reference_attached=True,
            refine_multimodal=True,
        ),
        l5_actions_ext=_build_l5_extensions(
            routing_enabled=routing_enabled,
            stack_root=stack_root,
            refine_mode=True,
            surgical_widgets=surgical_widgets,
        ),
        use_screen_ir=use_screen_ir,
    )

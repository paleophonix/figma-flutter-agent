"""ACDP prompt composition helpers."""

from __future__ import annotations

from figma_flutter_agent.llm.prompts.actions import (
    _L5_GENERATE_CUPERTINO,
    _L5_GENERATE_MATERIAL,
    _L5_GENERATE_ROUTING,
    _L5_GENERATE_STACK,
    _L5_REFINE,
    _L5_REFINE_SURGICAL,
)
from figma_flutter_agent.llm.prompts.capabilities import (
    _L4_GENERATE_CUPERTINO,
    _L4_GENERATE_MATERIAL,
)
from figma_flutter_agent.llm.prompts.environment import (
    _L5_SCREEN_IR_ARCHITECTURE,
    _L6_GENERATE_USER_CONTRACT,
    _L6_GENERATE_USER_CONTRACT_IR,
)
from figma_flutter_agent.llm.prompts.principles import (
    _L3_GENERATE_ROUTING_OFF,
    _L3_REFINE_MULTIMODAL,
    _L3_REFINE_VISUAL_GOLD,
    _generate_l3_core,
)
from figma_flutter_agent.llm.prompts.shared import (
    _L1_GENERATE_CUPERTINO,
    _L1_GENERATE_MATERIAL,
    _L2_GENERATE_CUPERTINO,
    _L2_GENERATE_MATERIAL,
    _join_sections,
)


def _acdp_layer(tag: str, body: str) -> str:
    """Wrap layer body in matching open/close ACDP tags.

    Args:
        tag: Layer tag name (e.g. ``L1:PURPOSE``).
        body: Inner text (no surrounding tags).

    Returns:
        Tagged block with explicit closing tag.
    """
    return f"<{tag}>\n{body.strip()}\n</{tag}>"


def _compose_acdp_prompt(
    *,
    l1: str,
    l2: str,
    l3_core: str,
    l3_principles_ext: str = "",
    l4: str,
    l5_core: str,
    l5_actions_ext: str = "",
    l6: str,
) -> str:
    """Assemble a system prompt with strict L1→L6 ordering and level-aware extensions.

    Conditional fragments are injected via ``l3_principles_ext`` and ``l5_actions_ext``
    inside their parent layers — never appended after ``<L6:ENVIRONMENT>``.

    Args:
        l1: ``<L1:PURPOSE>`` body text.
        l2: ``<L2:ROLE>`` body text.
        l3_core: Base ``<L3:PRINCIPLES>`` bullets (grammar, invariants).
        l3_principles_ext: Optional L3 extensions (visual gold, routing ban, refine multimodal).
        l4: ``<L4:CAPABILITIES>`` body text.
        l5_core: Base ``<L5:ACTIONS>`` numbered steps.
        l5_actions_ext: Optional L5 extensions (routing, stack root, refine, surgical).
        l6: ``<L6:ENVIRONMENT>`` block (static contract or Template-rendered repair context).

    Returns:
        Single system prompt preserving ACDP layer sequence.
    """
    l3_body = l3_core.strip()
    if l3_principles_ext.strip():
        l3_body = f"{l3_body}\n\n{l3_principles_ext.strip()}"
    l5_body = l5_core.strip()
    if l5_actions_ext.strip():
        l5_body = f"{l5_body}\n\n{l5_actions_ext.strip()}"
    return "\n\n".join(
        [
            _acdp_layer("L1:PURPOSE", l1),
            _acdp_layer("L2:ROLE", l2),
            _acdp_layer("L3:PRINCIPLES", l3_body),
            _acdp_layer("L4:CAPABILITIES", l4),
            _acdp_layer("L5:ACTIONS", l5_body),
            _acdp_layer("L6:ENVIRONMENT", l6),
        ]
    )


def _theme_layers(
    theme_variant: str,
    *,
    use_screen_ir: bool = False,
) -> tuple[str, str, str, str, str, str]:
    """Return base L1/L2/L3/L4/L5/L6 bodies for a generate theme variant."""
    l3 = _generate_l3_core(theme_variant, use_screen_ir=use_screen_ir)
    l6 = _L6_GENERATE_USER_CONTRACT_IR if use_screen_ir else _L6_GENERATE_USER_CONTRACT
    if theme_variant == "cupertino":
        return (
            _L1_GENERATE_CUPERTINO,
            _L2_GENERATE_CUPERTINO,
            l3,
            _L4_GENERATE_CUPERTINO,
            _L5_GENERATE_CUPERTINO,
            l6,
        )
    return (
        _L1_GENERATE_MATERIAL,
        _L2_GENERATE_MATERIAL,
        l3,
        _L4_GENERATE_MATERIAL,
        _L5_GENERATE_MATERIAL,
        l6,
    )


def _render_generate_prompt(
    theme_variant: str,
    *,
    l1_purpose: str | None = None,
    l3_principles_ext: str = "",
    l5_actions_ext: str = "",
    use_screen_ir: bool = False,
) -> str:
    """Render a generate/refine-base system prompt with placeholder injections at L3/L5."""
    l1, l2, l3, l4, l5, l6 = _theme_layers(theme_variant, use_screen_ir=use_screen_ir)
    if use_screen_ir:
        l5 = f"{l5}\n\n{_L5_SCREEN_IR_ARCHITECTURE}"
    return _compose_acdp_prompt(
        l1=l1_purpose or l1,
        l2=l2,
        l3_core=l3,
        l3_principles_ext=l3_principles_ext,
        l4=l4,
        l5_core=l5,
        l5_actions_ext=l5_actions_ext,
        l6=l6,
    )


def _build_l3_extensions(
    *,
    routing_enabled: bool,
    figma_reference_attached: bool,
    refine_multimodal: bool = False,
) -> str:
    """Collect L3 extensions in canonical order (routing ban → visual gold → refine)."""
    parts: list[str] = []
    if not routing_enabled:
        parts.append(_L3_GENERATE_ROUTING_OFF)
    if figma_reference_attached:
        parts.append(_L3_REFINE_VISUAL_GOLD)
    if refine_multimodal:
        parts.append(_L3_REFINE_MULTIMODAL)
    return _join_sections(*parts)


def _build_l5_extensions(
    *,
    routing_enabled: bool,
    stack_root: bool,
    refine_mode: bool = False,
    surgical_widgets: bool = False,
) -> str:
    """Collect L5 extensions in canonical order (routing → stack → refine → surgical)."""
    parts: list[str] = []
    if routing_enabled:
        parts.append(_L5_GENERATE_ROUTING)
    if stack_root:
        parts.append(_L5_GENERATE_STACK)
    if refine_mode:
        parts.append(_L5_REFINE)
    if surgical_widgets:
        parts.append(_L5_REFINE_SURGICAL)
    return _join_sections(*parts)

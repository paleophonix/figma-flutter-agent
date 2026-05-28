"""ACDP layer ordering for composed system prompts."""

from figma_flutter_agent.llm.prompts import (
    build_repair_system_prompt,
    build_system_prompt,
    build_visual_refine_system_prompt,
)


def _layer_index(prompt: str, marker: str) -> int:
    return prompt.index(marker)


def test_all_primary_layers_have_matching_close_tags() -> None:
    prompt = build_system_prompt(
        routing_enabled=True,
        figma_reference_attached=True,
        stack_root=True,
    )
    for tag in (
        "L1:PURPOSE",
        "L2:ROLE",
        "L3:PRINCIPLES",
        "L4:CAPABILITIES",
        "L5:ACTIONS",
        "L6:ENVIRONMENT",
    ):
        assert f"<{tag}>" in prompt
        assert f"</{tag}>" in prompt
        assert prompt.index(f"<{tag}>") < prompt.index(f"</{tag}>")

    repair = build_repair_system_prompt()
    assert "</L6:ENVIRONMENT>" in repair
    assert repair.count("<L1:PURPOSE>") == repair.count("</L1:PURPOSE>")


def test_conditional_fragments_stay_inside_l3_and_l5_before_l6() -> None:
    prompt = build_system_prompt(
        routing_enabled=True,
        figma_reference_attached=True,
        stack_root=True,
    )
    l3 = _layer_index(prompt, "<L3:PRINCIPLES>")
    l4 = _layer_index(prompt, "<L4:CAPABILITIES>")
    l5 = _layer_index(prompt, "<L5:ACTIONS>")
    l6 = _layer_index(prompt, "<L6:ENVIRONMENT>")
    visual_gold = _layer_index(prompt, "VISUAL GOLD STANDARD")
    routing_ext = _layer_index(prompt, "ROUTING COMPILATION")
    stack_ext = _layer_index(prompt, "STACK ROOT LAYOUT")

    assert l3 < visual_gold < l4
    assert l5 < routing_ext < stack_ext < l6
    assert "PRINCIPLES_VISUAL_GOLD" not in prompt
    assert "ACTIONS_ROUTING_EXT" not in prompt
    assert "ROUTING OUTPUT BAN" not in prompt


def test_routing_ban_in_l3_when_routing_disabled() -> None:
    prompt = build_system_prompt(routing_enabled=False)
    l3 = _layer_index(prompt, "<L3:PRINCIPLES>")
    l4 = _layer_index(prompt, "<L4:CAPABILITIES>")
    ban = _layer_index(prompt, "ROUTING OUTPUT BAN")
    assert l3 < ban < l4


def test_visual_refine_single_l1_and_no_post_l6_append() -> None:
    prompt = build_visual_refine_system_prompt(stack_root=True, surgical_widgets=True)
    assert prompt.count("<L1:PURPOSE>") == 1
    assert prompt.count("<L6:ENVIRONMENT>") == 1
    l1 = _layer_index(prompt, "<L1:PURPOSE>")
    l6 = _layer_index(prompt, "<L6:ENVIRONMENT>")
    refine_l3 = _layer_index(prompt, "TRIPLE COMPARISON MANDATE")
    surgical = _layer_index(prompt, "SURGICAL WIDGET MODE")
    assert l1 < refine_l3 < l6
    assert l1 < surgical < l6
    assert "Elite Multi-Modal UI Refinement Compiler" in prompt[prompt.index("<L1:PURPOSE>") : l6]

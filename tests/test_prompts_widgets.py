"""LLM prompt parity with deterministic semantic widget types."""

from figma_flutter_agent.llm.prompts import build_system_prompt


def test_material_prompt_covers_semantic_widget_types() -> None:
    prompt = build_system_prompt(theme_variant="material_3")

    assert "BOUNDED POSITIONED MANDATE" in prompt
    assert "GridView" in prompt
    assert "PageView" in prompt
    assert "BottomNavigationBar" in prompt
    assert "AlertDialog" in prompt
    assert "variantProperties" in prompt
    assert "STATEFUL VARIANT MAPPING" in prompt
    assert "INTERACTIVE COMPILER INVARIANT" in prompt
    assert "JSON SCHEMA GRAMMAR CONTROL" in prompt
    assert "decorative-only" in prompt
    assert "1:1 NODE PARITY LAW" in prompt
    assert "BUTTON DESIGN & ANTI-COLLISION" in prompt
    assert "ROOT GESTURE ISOLATION" in prompt
    assert "StackFit.expand" in prompt
    assert "CONDITIONAL TEXT DISPATCH" in prompt
    assert "<L1:PURPOSE>" in prompt
    assert "### cleanTree" in prompt


def test_stack_prompt_enforces_tree_and_button_invariants() -> None:
    prompt = build_system_prompt(theme_variant="material_3", stack_root=True)

    assert "STACK ROOT LAYOUT" in prompt
    assert "ValueKey('figma-" in prompt
    assert "comment placeholders" in prompt


def test_cupertino_prompt_covers_semantic_widget_types() -> None:
    prompt = build_system_prompt(theme_variant="cupertino")

    assert "Cupertino" in prompt
    assert "scrollAxis" in prompt
    assert "variantProperties" in prompt
    assert "CupertinoCheckbox" in prompt
    assert "INTERACTIVE COMPILER INVARIANT" in prompt
    assert "JSON SCHEMA GRAMMAR CONTROL" in prompt
    assert "1:1 NODE PARITY LAW" in prompt
    assert "ROOT GESTURE ISOLATION" in prompt

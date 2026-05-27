"""LLM prompt parity with deterministic semantic widget types."""

from figma_flutter_agent.llm.prompts import build_system_prompt


def test_material_prompt_covers_semantic_widget_types() -> None:
    prompt = build_system_prompt(theme_variant="material_3")

    assert "GridView" in prompt
    assert "PageView" in prompt
    assert "BottomNavigationBar" in prompt
    assert "AlertDialog" in prompt
    assert "variantProperties" in prompt
    assert "STATEFUL VARIANT MAPPING" in prompt
    assert "Interactive & Behavioral Compiler Invariants" in prompt
    assert "decorative-only" in prompt
    assert "PREBUILT VECTOR-RICH SUBTREES" in prompt


def test_cupertino_prompt_covers_semantic_widget_types() -> None:
    prompt = build_system_prompt(theme_variant="cupertino")

    assert "Cupertino" in prompt
    assert "scrollAxis" in prompt
    assert "variantProperties" in prompt
    assert "STATEFUL VARIANT MAPPING" in prompt
    assert "Interactive & Behavioral Compiler Invariants" in prompt
    assert "PREBUILT VECTOR-RICH SUBTREES" in prompt

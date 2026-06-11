"""LLM gray-zone annotation gate (E2.5-F)."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.presence.semantics import (
    sanitize_screen_ir_semantic_kinds,
    strip_screen_ir_classification_hints,
)
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.parser.semantics.classify import classify_screen_ir
from figma_flutter_agent.schemas import WidgetIrKind, WidgetIrNode
from figma_flutter_agent.schemas.ir_payloads import LlmClassificationHint
from tests.support.semantics_trees import filled_button


def _ir_with_llm_kind() -> tuple[object, object]:
    tree = filled_button()
    screen_ir = default_screen_ir(tree)
    screen_ir.root = screen_ir.root.model_copy(
        update={
            "kind": WidgetIrKind.BUTTON_FILLED,
            "classification_hint": LlmClassificationHint(
                suggested_kind="button_filled",
                confidence=0.9,
            ),
        },
    )
    return screen_ir, tree


def test_sanitize_drops_llm_hints_when_gray_zone_off() -> None:
    screen_ir, _ = _ir_with_llm_kind()
    sanitize_screen_ir_semantic_kinds(screen_ir, llm_gray_zone_enabled=False)
    assert screen_ir.root.kind == WidgetIrKind.AUTO
    assert screen_ir.root.classification_hint is None


def test_sanitize_preserves_hint_when_gray_zone_on() -> None:
    screen_ir, _ = _ir_with_llm_kind()
    sanitize_screen_ir_semantic_kinds(screen_ir, llm_gray_zone_enabled=True, grey_zone_min=0.5)
    assert screen_ir.root.kind == WidgetIrKind.AUTO
    assert screen_ir.root.classification_hint is not None
    assert screen_ir.root.classification_hint.suggested_kind == "button_filled"


def test_classify_ignores_llm_hint_when_gray_zone_off() -> None:
    screen_ir, tree = _ir_with_llm_kind()
    updated, report = classify_screen_ir(screen_ir, tree, llm_gray_zone_enabled=False)
    assert report.semantic is not None
    assert report.semantic.llm_annotation_used == []
    kind = _find_kind(updated.root, "btn-filled")
    assert kind == WidgetIrKind.AUTO.value or kind == WidgetIrKind.BUTTON_FILLED.value


def test_strip_classification_hints() -> None:
    screen_ir, _ = _ir_with_llm_kind()
    count = strip_screen_ir_classification_hints(screen_ir)
    assert count == 1
    assert screen_ir.root.classification_hint is None


def _find_kind(node: WidgetIrNode, figma_id: str) -> str:
    if node.figma_id == figma_id:
        return node.kind.value
    for child in node.children:
        found = _find_kind(child, figma_id)
        if found:
            return found
    return ""

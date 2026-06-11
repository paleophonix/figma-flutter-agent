"""Strip authoritative semantic kinds assigned by the LLM before classification."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
from figma_flutter_agent.schemas import ScreenIr, WidgetIrKind, WidgetIrNode
from figma_flutter_agent.schemas.ir_payloads import LlmClassificationHint


def sanitize_screen_ir_semantic_kinds(
    screen_ir: ScreenIr,
    *,
    grey_zone_min: float = 0.5,
    llm_gray_zone_enabled: bool = False,
) -> int:
    """Reset LLM semantic kinds to ``auto`` before authoritative classification.

    When ``llm_gray_zone_enabled`` is True, preserve the kind as a grey-zone hint.
    When False (default), hints are dropped so the classifier ignores LLM semantics.

    Args:
        screen_ir: Mutable screen IR graph.
        grey_zone_min: Default hint confidence when the LLM did not provide one.
        llm_gray_zone_enabled: Whether to retain ``classificationHint`` from LLM kinds.

    Returns:
        Count of nodes downgraded from semantic kinds to ``auto``.
    """
    downgraded = 0

    def walk(node: WidgetIrNode) -> WidgetIrNode:
        nonlocal downgraded
        children = [walk(child) for child in node.children]
        if node.kind not in SEMANTIC_IR_KINDS:
            return node.model_copy(update={"children": children})
        downgraded += 1
        hint = None
        if llm_gray_zone_enabled:
            hint = node.classification_hint or LlmClassificationHint(
                suggested_kind=node.kind.value,
                confidence=grey_zone_min,
            )
        return node.model_copy(
            update={
                "kind": WidgetIrKind.AUTO,
                "classification_hint": hint,
                "children": children,
            },
        )

    screen_ir.root = walk(screen_ir.root)
    return downgraded


def strip_screen_ir_classification_hints(screen_ir: ScreenIr) -> int:
    """Remove all ``classificationHint`` fields when LLM gray-zone is disabled."""
    stripped = 0

    def walk(node: WidgetIrNode) -> WidgetIrNode:
        nonlocal stripped
        children = [walk(child) for child in node.children]
        if node.classification_hint is None:
            return node.model_copy(update={"children": children})
        stripped += 1
        return node.model_copy(
            update={"classification_hint": None, "children": children},
        )

    screen_ir.root = walk(screen_ir.root)
    return stripped

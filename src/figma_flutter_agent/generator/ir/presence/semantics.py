"""Strip authoritative semantic kinds assigned by the LLM before classification."""

from __future__ import annotations

from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
from figma_flutter_agent.schemas import ScreenIr, WidgetIrKind, WidgetIrNode
from figma_flutter_agent.schemas.ir_payloads import LlmClassificationHint


def sanitize_screen_ir_semantic_kinds(screen_ir: ScreenIr, *, grey_zone_min: float = 0.5) -> int:
    """Move LLM semantic kinds into grey-zone hints and reset nodes to ``auto``.

    Args:
        screen_ir: Mutable screen IR graph.
        grey_zone_min: Default hint confidence when the LLM did not provide one.

    Returns:
        Count of nodes downgraded from semantic kinds to ``auto``.
    """
    downgraded = 0

    def walk(node: WidgetIrNode) -> WidgetIrNode:
        nonlocal downgraded
        children = [walk(child) for child in node.children]
        if node.kind not in SEMANTIC_IR_KINDS:
            return node.model_copy(update={"children": children})
        hint = node.classification_hint or LlmClassificationHint(
            suggested_kind=node.kind.value,
            confidence=grey_zone_min,
        )
        downgraded += 1
        return node.model_copy(
            update={
                "kind": WidgetIrKind.AUTO,
                "classification_hint": hint,
                "children": children,
            },
        )

    screen_ir.root = walk(screen_ir.root)
    return downgraded

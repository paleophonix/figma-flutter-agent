"""LLM payload helpers for screen intermediate representation."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.generator.ir.states import derive_state_by_figma_id
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.schemas import CleanDesignTreeNode, WidgetIrNode


def dump_screen_ir_blueprint(root: CleanDesignTreeNode) -> dict[str, Any]:
    """Return a canonical ``screenIr`` skeleton the model should refine, not replace."""
    blueprint = default_screen_ir(root).model_dump(by_alias=True, mode="json")
    states = derive_state_by_figma_id(root)
    if states:
        blueprint["stateByFigmaId"] = {figma_id: state.value for figma_id, state in states.items()}
    blueprint.setdefault("adaptiveRules", [])
    return blueprint


def _compact_widget_ir_node(node: WidgetIrNode) -> dict[str, Any]:
    """Minimal figmaId tree for LLM payloads when ``cleanTree`` is also present."""
    payload: dict[str, Any] = {"figmaId": node.figma_id}
    if node.children:
        payload["children"] = [_compact_widget_ir_node(child) for child in node.children]
    return payload


def dump_screen_ir_blueprint_for_llm(root: CleanDesignTreeNode) -> dict[str, Any]:
    """Return a compact ``screenIr`` skeleton (structure + states only).

    When ``### cleanTree`` is in the user payload, omit default ``kind: auto`` on every node.
    """
    blueprint: dict[str, Any] = {"root": _compact_widget_ir_node(default_screen_ir(root).root)}
    states = derive_state_by_figma_id(root)
    if states:
        blueprint["stateByFigmaId"] = {figma_id: state.value for figma_id, state in states.items()}
    return blueprint


def dump_widget_ir_blueprint(subtree: CleanDesignTreeNode) -> dict[str, Any]:
    """Return a canonical ``widgetIr`` skeleton for one extracted subtree root."""
    return WidgetIrNode(
        figma_id=subtree.id,
        children=[WidgetIrNode(figma_id=child.id) for child in subtree.children],
    ).model_dump(by_alias=True, mode="json")

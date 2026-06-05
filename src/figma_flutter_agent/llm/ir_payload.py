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
        blueprint["stateByFigmaId"] = {
            figma_id: state.value for figma_id, state in states.items()
        }
    blueprint.setdefault("adaptiveRules", [])
    return blueprint


def dump_widget_ir_blueprint(subtree: CleanDesignTreeNode) -> dict[str, Any]:
    """Return a canonical ``widgetIr`` skeleton for one extracted subtree root."""
    return WidgetIrNode(
        figma_id=subtree.id,
        children=[
            WidgetIrNode(figma_id=child.id)
            for child in subtree.children
        ],
    ).model_dump(by_alias=True, mode="json")

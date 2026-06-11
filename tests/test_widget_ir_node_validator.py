"""WidgetIrNode constructor and payload validator contract."""

from __future__ import annotations

import warnings

from figma_flutter_agent.schemas import WidgetIrKind, WidgetIrNode


def test_widget_ir_node_init_sets_semantic_payload_without_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        node = WidgetIrNode(
            figma_id="chip-1",
            kind=WidgetIrKind.CHIP_CHOICE,
            is_selected=True,
        )
    assert node.payload is not None
    assert node.is_selected is True

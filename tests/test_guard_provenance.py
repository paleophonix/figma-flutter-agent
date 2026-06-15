"""Guard mutation provenance (E2.5-B)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.provenance import (
    activate_provenance_recorder,
    clear_provenance_recorder,
    get_provenance_recorder,
)
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.ir.validate import _apply_ir_guards_inplace, apply_ir_guards
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, SizingMode
from tests.support.semantics_trees import filled_button


def test_min_touch_target_recorded_in_provenance() -> None:
    tree = filled_button()
    tree = tree.model_copy(
        update={
            "sizing": Sizing(
                width=30.0, height=30.0, width_mode=SizingMode.FIXED, height_mode=SizingMode.FIXED
            ),
        },
    )
    screen_ir = default_screen_ir(tree)
    activate_provenance_recorder(feature_name="guard_test", project_dir=Path("."))
    try:
        apply_ir_guards(screen_ir, tree)
        recorder = get_provenance_recorder()
        assert recorder is not None
        transforms = {item.transform for item in recorder.mutations}
        assert "min_touch_target_guard" in transforms
        assert any(item.checkpoint == "CP1_guards" for item in recorder.mutations)
    finally:
        clear_provenance_recorder()


def test_keyboard_scroll_guard_recorded() -> None:
    input_node = CleanDesignTreeNode(
        id="input-low",
        name="field",
        type=NodeType.INPUT,
        sizing=Sizing(width=280.0, height=48.0),
        offset_y=500.0,
    )
    column = CleanDesignTreeNode(
        id="form-col",
        name="column",
        type=NodeType.COLUMN,
        sizing=Sizing(width=320.0, height=600.0),
        children=[input_node],
    )
    root = CleanDesignTreeNode(
        id="screen",
        name="screen",
        type=NodeType.COLUMN,
        sizing=Sizing(width=360.0, height=640.0),
        children=[column],
    )
    screen_ir = default_screen_ir(root)
    activate_provenance_recorder(feature_name="keyboard_scroll", project_dir=Path("."))
    try:
        _apply_ir_guards_inplace(screen_ir, root)
        recorder = get_provenance_recorder()
        assert recorder is not None
        transforms = {item.transform for item in recorder.mutations}
        assert "keyboard_scroll_guard" in transforms
    finally:
        clear_provenance_recorder()

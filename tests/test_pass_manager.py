"""PassManager and IR pass registry tests."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes import (
    WAVE_1_IR_PASSES,
    PassManager,
    apply_ir_layout_passes,
)
from figma_flutter_agent.generator.ir.passes.registry import (
    _run_scroll_host,
    _run_unpin,
    _run_unstack,
)
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.tree_copy import hash_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


def _simple_column() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.COLUMN,
        sizing={"width": 360.0, "height": 800.0},
        children=[
            CleanDesignTreeNode(
                id="title",
                name="Title",
                type=NodeType.TEXT,
                text="Hello",
                sizing={"width": 200.0, "height": 24.0},
            ),
        ],
    )


def test_wave_1_registry_has_three_passes() -> None:
    assert tuple(pass_.name for pass_ in WAVE_1_IR_PASSES) == (
        "unstack",
        "unpin",
        "scroll_host",
    )


def test_pass_manager_runs_in_registry_order() -> None:
    seen: list[str] = []

    class RecordingManager(PassManager):
        def run(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            for registered in self._passes:
                seen.append(registered.name)
            return super().run(*args, **kwargs)

    tree = _simple_column()
    screen_ir = default_screen_ir(tree)
    RecordingManager().run(screen_ir, tree, validate_cp2=False)
    assert seen == ["unstack", "unpin", "scroll_host"]


def test_apply_ir_layout_passes_idempotent_second_run() -> None:
    tree = _simple_column()
    screen_ir = default_screen_ir(tree)
    first_ir, first_clean = apply_ir_layout_passes(
        screen_ir,
        tree,
        inject_root_scroll_host=True,
        validate_cp2=False,
    )
    before_hash = hash_clean_tree(first_clean)
    second_ir, second_clean = apply_ir_layout_passes(
        first_ir,
        first_clean,
        inject_root_scroll_host=True,
        validate_cp2=False,
    )
    assert hash_clean_tree(second_clean) == before_hash
    assert second_ir.model_dump() == first_ir.model_dump()


def test_pass_callables_return_updated_context() -> None:
    from figma_flutter_agent.generator.ir.passes.protocol import PassContext

    tree = _simple_column()
    screen_ir = default_screen_ir(tree)
    ctx = PassContext(screen_ir=screen_ir, clean_tree=tree)
    for runner in (_run_unstack, _run_unpin, _run_scroll_host):
        ctx = runner(ctx)
    assert ctx.clean_tree.id == "root"
    assert ctx.screen_ir.root.figma_id == "root"

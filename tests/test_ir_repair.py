"""Tests for screen IR repair patches and materialize precedence."""

from __future__ import annotations

from figma_flutter_agent.generator.ir_emitter import materialize_screen_code_from_ir
from figma_flutter_agent.generator.ir_repair import apply_ir_patch_to_screen
from figma_flutter_agent.generator.ir_tree import default_screen_ir
from figma_flutter_agent.llm.repair_apply import apply_repair_patches
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FlutterGenerationResponse,
    FlutterRepairIrPatch,
    FlutterRepairPatch,
    FlutterRepairPatchResponse,
    NodeType,
    ScreenIr,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrOverrides,
)


def test_apply_ir_patch_overrides_text() -> None:
    root = CleanDesignTreeNode(
        id="1",
        name="Col",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="2", name="T", type=NodeType.TEXT, text="Hi"),
        ],
    )
    screen_ir = default_screen_ir(root)
    updated = apply_ir_patch_to_screen(
        screen_ir,
        figma_id="2",
        overrides=WidgetIrOverrides(text="Bye"),
    )
    assert updated.root.children[0].overrides is not None
    assert updated.root.children[0].overrides.text == "Bye"


def test_apply_ir_patch_reorder_children() -> None:
    root = CleanDesignTreeNode(
        id="1",
        name="Row",
        type=NodeType.ROW,
        children=[
            CleanDesignTreeNode(id="a", name="A", type=NodeType.TEXT, text="A"),
            CleanDesignTreeNode(id="b", name="B", type=NodeType.TEXT, text="B"),
        ],
    )
    screen_ir = default_screen_ir(root)
    updated = apply_ir_patch_to_screen(
        screen_ir,
        figma_id="1",
        reorder_children=["b", "a"],
    )
    ids = [child.figma_id for child in updated.root.children]
    assert ids == ["b", "a"]


def test_apply_repair_ir_patch_clears_stale_screen_code() -> None:
    root = CleanDesignTreeNode(id="1", name="R", type=NodeType.ROW, children=[])
    screen_ir = default_screen_ir(root)
    current = FlutterGenerationResponse(
        screen_ir=screen_ir,
        screen_code="stale dart",
        extracted_widgets=[],
    )
    outcome = apply_repair_patches(
        current,
        FlutterRepairPatchResponse(
            ir_patches=[
                FlutterRepairIrPatch(
                    figmaId="1",
                    overrides=WidgetIrOverrides(accessibility_label="screen"),
                )
            ],
        ),
        clean_tree=root,
    )
    assert outcome.ir_patches_applied == 1
    assert outcome.generation.screen_code is None
    assert outcome.generation.screen_ir is not None


def test_apply_repair_dart_patch_clears_screen_ir() -> None:
    root = CleanDesignTreeNode(id="1", name="R", type=NodeType.ROW, children=[])
    screen_ir = default_screen_ir(root)
    current = FlutterGenerationResponse(
        screen_ir=screen_ir,
        screen_code="line one\nline two\n",
        extracted_widgets=[],
    )
    diff = (
        "@@ -1,2 +1,2 @@\n"
        " line one\n"
        "-line two\n"
        "+line TWO\n"
    )
    outcome = apply_repair_patches(
        current,
        FlutterRepairPatchResponse(
            patches=[FlutterRepairPatch(target="screenCode", code=diff)],
        ),
        base_sources={"lib/features/x/x_screen.dart": current.screen_code or ""},
        target_planned_paths={("screenCode", None): "lib/features/x/x_screen.dart"},
    )
    assert outcome.patches_applied == 1
    assert outcome.generation.screen_ir is None
    assert "line TWO" in (outcome.generation.screen_code or "")


def test_materialize_skips_when_screen_code_present() -> None:
    root = CleanDesignTreeNode(id="1", name="R", type=NodeType.ROW, children=[])
    screen_ir = default_screen_ir(root)
    generation = FlutterGenerationResponse(
        screen_ir=screen_ir,
        screen_code="@RoutePage()\nclass X {}",
        extracted_widgets=[],
    )
    from figma_flutter_agent.generator.ir_emitter import IrEmitContext

    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    out = materialize_screen_code_from_ir(
        generation,
        clean_tree=root,
        feature_name="x",
        ctx=ctx,
        prefer_existing_screen_code=True,
    )
    assert out.screen_code == generation.screen_code


def test_materialize_runs_when_screen_code_cleared() -> None:
    root = CleanDesignTreeNode(
        id="1",
        name="Col",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="2", name="T", type=NodeType.TEXT, text="Hi"),
        ],
    )
    screen_ir = default_screen_ir(root)
    generation = FlutterGenerationResponse(screen_ir=screen_ir, extracted_widgets=[])
    from figma_flutter_agent.generator.ir_emitter import IrEmitContext

    ctx = IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True)
    out = materialize_screen_code_from_ir(
        generation,
        clean_tree=root,
        feature_name="demo",
        ctx=ctx,
    )
    assert out.resolved_screen_code()
    assert "DemoScreen" in out.screen_code

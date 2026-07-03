"""ExtractedRefTerminalLaw — screen IR extracted nodes are opaque leaves."""

from __future__ import annotations

import pytest

from figma_flutter_agent.generator.ir.presence import normalize_screen_ir_presence
from figma_flutter_agent.generator.ir.validate import validate_screen_ir
from figma_flutter_agent.generator.ir.validate.graph import (
    enforce_extracted_screen_ir_terminals,
    ensure_ir_direct_children_match_clean,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeType,
    ScreenIr,
    Sizing,
    SizingMode,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrRef,
)


def _composite_card_tree() -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        children=[
            CleanDesignTreeNode(
                id="card:1",
                name="Card",
                type=NodeType.STACK,
                sizing=Sizing(width=327.0, height=141.0),
                children=[
                    CleanDesignTreeNode(
                        id="card:1:bg",
                        name="Background",
                        type=NodeType.CONTAINER,
                        sizing=Sizing(width=327.0, height=141.0),
                    ),
                    CleanDesignTreeNode(
                        id="card:1:row",
                        name="Row",
                        type=NodeType.ROW,
                        children=[
                            CleanDesignTreeNode(
                                id="card:1:icon",
                                name="Icon",
                                type=NodeType.VECTOR,
                                sizing=Sizing(width=20.0, height=20.0),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _extracted_screen_ir() -> ScreenIr:
    return ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="card:1",
                    kind=WidgetIrKind.EXTRACTED,
                    children=[],
                    ref=WidgetIrRef(widget_name="GroupCardWidget"),
                ),
            ],
        ),
    )


def _composite_card_clean(*, node_id: str = "card:1", top: float = 360.0) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Card",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=327.0,
            height=141.0,
        ),
        stack_placement=StackPlacement(left=24.0, top=top, width=327.0, height=141.0),
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=24.0, y=top, width=327.0, height=141.0),
        ),
        children=[
            CleanDesignTreeNode(
                id=f"{node_id}:bg",
                name="Background",
                type=NodeType.CONTAINER,
                sizing=Sizing(width=327.0, height=141.0),
            ),
            CleanDesignTreeNode(
                id=f"{node_id}:row",
                name="Row",
                type=NodeType.ROW,
                children=[
                    CleanDesignTreeNode(
                        id=f"{node_id}:icon",
                        name="Icon",
                        type=NodeType.VECTOR,
                        sizing=Sizing(width=20.0, height=20.0),
                    ),
                ],
            ),
        ],
    )


def _section_child(
    node_id: str,
    *,
    top: float,
    height: float,
    node_type: NodeType = NodeType.TEXT,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=node_type,
        text="label" if node_type == NodeType.TEXT else None,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=327.0,
            height=height,
        ),
        stack_placement=StackPlacement(left=24.0, top=top, width=327.0, height=height),
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=24.0, y=top, width=327.0, height=height),
        ),
    )


def _sectionizable_extracted_fixture() -> tuple[CleanDesignTreeNode, ScreenIr]:
    clean = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=375.0,
            height=903.0,
        ),
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=0.0, y=0.0, width=375.0, height=903.0),
        ),
        children=[
            _section_child("hero", top=100.0, height=180.0, node_type=NodeType.STACK),
            _section_child("title", top=300.0, height=40.0),
            _composite_card_clean(node_id="card:1", top=360.0),
            _section_child("footer", top=620.0, height=200.0, node_type=NodeType.STACK),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(figma_id="hero", kind=WidgetIrKind.AUTO),
                WidgetIrNode(figma_id="title", kind=WidgetIrKind.AUTO),
                WidgetIrNode(
                    figma_id="card:1",
                    kind=WidgetIrKind.EXTRACTED,
                    children=[],
                    ref=WidgetIrRef(widget_name="GroupCardWidget"),
                ),
                WidgetIrNode(figma_id="footer", kind=WidgetIrKind.AUTO),
            ],
        ),
    )
    return clean, screen_ir


def _find_ir_node(root: WidgetIrNode, figma_id: str) -> WidgetIrNode | None:
    if root.figma_id == figma_id:
        return root
    for child in root.children:
        found = _find_ir_node(child, figma_id)
        if found is not None:
            return found
    return None


def _assert_extracted_boundary(screen_ir: ScreenIr, figma_id: str, widget_name: str) -> None:
    node = _find_ir_node(screen_ir.root, figma_id)
    assert node is not None
    assert node.kind == WidgetIrKind.EXTRACTED
    assert node.children == []
    assert node.ref is not None
    assert node.ref.widget_name == widget_name


def test_ensure_ir_direct_children_match_clean_skips_extracted_terminal() -> None:
    tree = _composite_card_tree()
    screen_ir = _extracted_screen_ir()
    inserted = ensure_ir_direct_children_match_clean(screen_ir, tree)
    assert inserted == 0
    assert screen_ir.root.children[0].children == []


def test_normalize_presence_keeps_valid_extracted_terminal() -> None:
    tree = _composite_card_tree()
    screen_ir = _extracted_screen_ir()
    normalized = normalize_screen_ir_presence(
        screen_ir,
        tree,
        extracted_widget_names=frozenset({"GroupCardWidget"}),
    )
    extracted = normalized.root.children[0]
    assert extracted.kind == WidgetIrKind.EXTRACTED
    assert extracted.ref is not None
    assert extracted.ref.widget_name == "GroupCardWidget"
    assert extracted.children == []


def test_validate_screen_ir_passes_after_graph_sync_for_extracted_card() -> None:
    tree = _composite_card_tree()
    screen_ir = _extracted_screen_ir()
    normalized = normalize_screen_ir_presence(
        screen_ir,
        tree,
        extracted_widget_names=frozenset({"GroupCardWidget"}),
    )
    validate_screen_ir(
        normalized,
        tree,
        extracted_widget_names=frozenset({"GroupCardWidget"}),
        declared_extracted_widget_names=frozenset({"GroupCardWidget"}),
        apply_guards=False,
        skip_presence_normalize=True,
    )


def test_invalid_extracted_ref_downgrades_and_receives_clean_children() -> None:
    from figma_flutter_agent.generator.ir.presence.sanitize import (
        sanitize_screen_ir_extracted_refs,
    )

    tree = _composite_card_tree()
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="card:1",
                    kind=WidgetIrKind.EXTRACTED,
                    children=[],
                    ref=WidgetIrRef(widget_name="MissingWidget"),
                ),
            ],
        ),
    )
    downgraded, _ = sanitize_screen_ir_extracted_refs(
        screen_ir,
        tree,
        extracted_widget_names=frozenset({"OtherWidget"}),
        canonical_extracted_widget_names=frozenset({"OtherWidget"}),
    )
    assert downgraded == 1
    card_ir = screen_ir.root.children[0]
    assert card_ir.kind != WidgetIrKind.EXTRACTED
    inserted = ensure_ir_direct_children_match_clean(screen_ir, tree)
    assert inserted > 0
    assert card_ir.children


def test_check_graph_sync_allows_extracted_terminal_with_clean_subtree() -> None:
    from figma_flutter_agent.generator.geometry.invariants.conservation import check_graph_sync

    tree = _composite_card_tree()
    screen_ir = _extracted_screen_ir()
    assert not check_graph_sync(screen_ir, tree)


def test_check_graph_sync_rejects_extracted_host_with_inline_children() -> None:
    from figma_flutter_agent.generator.geometry.invariants.conservation import check_graph_sync

    tree = _composite_card_tree()
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="card:1",
                    kind=WidgetIrKind.EXTRACTED,
                    children=[WidgetIrNode(figma_id="card:1:bg", kind=WidgetIrKind.AUTO)],
                    ref=WidgetIrRef(widget_name="GroupCardWidget"),
                ),
            ],
        ),
    )
    violations = check_graph_sync(screen_ir, tree)
    assert any(
        item.node_id == "card:1" and "inline IR children" in item.detail for item in violations
    )


def test_enforce_extracted_terminals_clears_zombie_children_before_validate() -> None:
    tree = _composite_card_tree()
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="root",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="card:1",
                    kind=WidgetIrKind.EXTRACTED,
                    children=[WidgetIrNode(figma_id="card:1:bg", kind=WidgetIrKind.AUTO)],
                    ref=WidgetIrRef(widget_name="GroupCardWidget"),
                ),
            ],
        ),
    )
    stripped = enforce_extracted_screen_ir_terminals(screen_ir.root)
    assert stripped == 1
    assert screen_ir.root.children[0].children == []
    validate_screen_ir(
        screen_ir,
        tree,
        extracted_widget_names=frozenset({"GroupCardWidget"}),
        declared_extracted_widget_names=frozenset({"GroupCardWidget"}),
        apply_guards=False,
        skip_presence_normalize=True,
    )


def test_sectionize_preserves_extracted_boundary() -> None:
    from figma_flutter_agent.generator.geometry.invariants.conservation import check_graph_sync
    from figma_flutter_agent.generator.ir.passes.sectionize import sectionize_root_stack

    clean, screen_ir = _sectionizable_extracted_fixture()
    updated_ir, updated_clean = sectionize_root_stack(screen_ir, clean)
    _assert_extracted_boundary(updated_ir, "card:1", "GroupCardWidget")
    assert not check_graph_sync(updated_ir, updated_clean)


def test_check_graph_sync_rejects_orphan_ref_on_inline_kind() -> None:
    from figma_flutter_agent.generator.geometry.invariants.conservation import check_graph_sync

    clean, screen_ir = _sectionizable_extracted_fixture()
    screen_ir.root.children[2] = screen_ir.root.children[2].model_copy(
        update={"kind": WidgetIrKind.STACK},
    )
    violations = check_graph_sync(screen_ir, clean)
    assert any(
        item.node_id == "card:1" and "extracted widget ref" in item.detail for item in violations
    )


@pytest.mark.parametrize(
    "runner_name",
    ["sectionize", "unstack", "unpin", "scroll_host"],
)
def test_layout_passes_preserve_extracted_boundary(runner_name: str) -> None:
    from figma_flutter_agent.generator.geometry.invariants.conservation import check_graph_sync
    from figma_flutter_agent.generator.ir.passes import WAVE_1_IR_PASSES
    from figma_flutter_agent.generator.ir.passes.protocol import PassContext

    clean, screen_ir = _sectionizable_extracted_fixture()
    runner = next(pass_ for pass_ in WAVE_1_IR_PASSES if pass_.name == runner_name)
    ctx = PassContext(screen_ir=screen_ir, clean_tree=clean, inject_root_scroll_host=True)
    ctx = runner.run(ctx)
    _assert_extracted_boundary(ctx.screen_ir, "card:1", "GroupCardWidget")
    assert not check_graph_sync(ctx.screen_ir, ctx.clean_tree)


def test_apply_ir_layout_passes_food_menu_2_extracted_boundaries() -> None:
    import json
    from pathlib import Path

    from figma_flutter_agent.generator.geometry.invariants.conservation import check_graph_sync
    from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes

    artifact = Path(".debug/screen/limbo/food_menu_2/llm_validated.json")
    processed = Path(".debug/screen/limbo/food_menu_2/processed.json")
    if not artifact.is_file() or not processed.is_file():
        return

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    proc = json.loads(processed.read_text(encoding="utf-8"))
    clean = CleanDesignTreeNode.model_validate(proc["cleanTree"])
    screen_ir = ScreenIr.model_validate(payload["screenIr"])
    updated_ir, updated_clean = apply_ir_layout_passes(
        screen_ir,
        clean,
        macro_height_threshold_px=900,
        validate_cp2=True,
    )
    for figma_id, widget_name in (
        ("602:764", "Group3362Widget"),
        ("602:823", "Group8264Widget"),
        ("602:791", "IconRightWidget"),
        ("602:809", "IconRightWidget2"),
    ):
        _assert_extracted_boundary(updated_ir, figma_id, widget_name)
    assert not check_graph_sync(updated_ir, updated_clean)

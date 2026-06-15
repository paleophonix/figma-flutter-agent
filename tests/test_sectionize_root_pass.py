"""Tests for LAW-SCREEN-SECTIONIZE root pass."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.passes.sectionize import evaluate_root_sectionize
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    GeometryFrame,
    GeomRect,
    NodeType,
    Sizing,
    SizingMode,
    StackPlacement,
)


def _section_child(
    node_id: str,
    *,
    top: float,
    height: float,
    width: float = 327.0,
    node_type: NodeType = NodeType.TEXT,
    text: str = "label",
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=node_type,
        text=text if node_type == NodeType.TEXT else None,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=width,
            height=height,
        ),
        stack_placement=StackPlacement(left=24.0, top=top, width=width, height=height),
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=24.0, y=top, width=width, height=height),
        ),
    )


def _vertical_sections_root(*, with_bottom_panel: bool = False) -> CleanDesignTreeNode:
    children = [
        _section_child("hero", top=100.0, height=180.0, node_type=NodeType.STACK),
        _section_child("title", top=300.0, height=40.0, text="Title"),
        _section_child("chips", top=360.0, height=48.0, node_type=NodeType.STACK),
    ]
    if with_bottom_panel:
        children.append(
            CleanDesignTreeNode(
                id="purchase",
                name="purchase",
                type=NodeType.STACK,
                sizing=Sizing(
                    width_mode=SizingMode.FIXED,
                    height_mode=SizingMode.FIXED,
                    width=375.0,
                    height=120.0,
                ),
                stack_placement=StackPlacement(
                    left=0.0,
                    bottom=0.0,
                    width=375.0,
                    height=120.0,
                    vertical="BOTTOM",
                ),
                geometry_frame=GeometryFrame(
                    layout_rect=GeomRect(x=0.0, y=783.0, width=375.0, height=120.0),
                ),
            ),
        )
    return CleanDesignTreeNode(
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
        children=children,
    )


def test_evaluate_root_sectionize_activates_for_vertical_sections() -> None:
    plan = evaluate_root_sectionize(
        _vertical_sections_root(),
        responsive_reflow_enabled=True,
    )
    assert plan.activated is True
    assert len(plan.scroll_sections) == 3


def test_sectionize_converts_root_stack_to_column() -> None:
    clean = _vertical_sections_root()
    screen_ir = default_screen_ir(clean)
    _, updated_clean = apply_ir_layout_passes(
        screen_ir,
        clean,
        inject_root_scroll_host=True,
        validate_cp2=False,
    )
    assert updated_clean.type == NodeType.COLUMN
    assert updated_clean.children[0].stack_placement is None


def test_sectionize_emits_scroll_without_root_fitted_box() -> None:
    clean = _vertical_sections_root(with_bottom_panel=True)
    screen_ir = default_screen_ir(clean)
    _, updated_clean = apply_ir_layout_passes(
        screen_ir,
        clean,
        inject_root_scroll_host=True,
        validate_cp2=False,
    )
    body = render_node_body(
        updated_clean,
        uses_svg=False,
        is_layout_root=True,
        responsive_enabled=True,
    )
    assert "SingleChildScrollView" in body
    assert "FittedBox(fit: BoxFit.scaleDown" not in body


def test_sectionize_rejects_single_section_without_bottom_chrome() -> None:
    clean = CleanDesignTreeNode(
        id="root",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=375.0,
            height=812.0,
        ),
        geometry_frame=GeometryFrame(
            world_aabb=GeomRect(x=0.0, y=0.0, width=375.0, height=812.0),
        ),
        children=[
            _section_child("only", top=100.0, height=200.0),
            _section_child("overlap", top=150.0, height=200.0),
        ],
    )
    plan = evaluate_root_sectionize(clean, responsive_reflow_enabled=True)
    assert plan.activated is False


def test_chip_row_inside_section_still_unstacks_to_row() -> None:
    chip_row = CleanDesignTreeNode(
        id="chip-row",
        name="chip-row",
        type=NodeType.STACK,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=216.0, height=48.0),
        stack_placement=StackPlacement(left=24.0, top=360.0, width=216.0, height=48.0),
        children=[
            CleanDesignTreeNode(
                id="c1",
                name="c1",
                type=NodeType.BUTTON,
                sizing=Sizing(width=48.0, height=48.0),
                stack_placement=StackPlacement(left=0.0, top=0.0, width=48.0, height=48.0),
                geometry_frame=GeometryFrame(
                    layout_rect=GeomRect(x=0.0, y=0.0, width=48.0, height=48.0),
                ),
            ),
            CleanDesignTreeNode(
                id="c2",
                name="c2",
                type=NodeType.BUTTON,
                sizing=Sizing(width=48.0, height=48.0),
                stack_placement=StackPlacement(left=56.0, top=0.0, width=48.0, height=48.0),
                geometry_frame=GeometryFrame(
                    layout_rect=GeomRect(x=56.0, y=0.0, width=48.0, height=48.0),
                ),
            ),
        ],
    )
    clean = _vertical_sections_root()
    clean = clean.model_copy(
        update={
            "children": [
                clean.children[0],
                clean.children[1],
                chip_row,
            ],
        },
    )
    screen_ir = default_screen_ir(clean)
    _, updated_clean = apply_ir_layout_passes(
        screen_ir,
        clean,
        validate_cp2=False,
    )
    chip_node = _find_node(updated_clean, "chip-row")
    assert chip_node is not None
    assert chip_node.type in {NodeType.ROW, NodeType.WRAP}


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None

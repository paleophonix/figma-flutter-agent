"""Tests for LAW-SCREEN-SECTIONIZE root pass."""

from __future__ import annotations

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_stack_paint_order_preserved,
)
from figma_flutter_agent.generator.geometry.invariants.validate import (
    validate_geometry_invariants,
)
from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes
from figma_flutter_agent.generator.ir.passes.sectionize import (
    evaluate_root_sectionize,
    sectionize_root_stack,
)
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


def _metric_peer_stack(
    node_id: str,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    inner_id: str,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=NodeType.STACK,
        sizing=Sizing(
            width_mode=SizingMode.FIXED,
            height_mode=SizingMode.FIXED,
            width=width,
            height=height,
        ),
        stack_placement=StackPlacement(left=left, top=top, width=width, height=height),
        geometry_frame=GeometryFrame(
            layout_rect=GeomRect(x=left, y=top, width=width, height=height),
        ),
        children=[
            CleanDesignTreeNode(
                id=inner_id,
                name=inner_id,
                type=NodeType.TEXT,
                text=inner_id,
                sizing=Sizing(width=width - 30.0, height=height - 3.0),
                stack_placement=StackPlacement(
                    left=30.0,
                    top=1.5,
                    width=width - 30.0,
                    height=height - 3.0,
                ),
                geometry_frame=GeometryFrame(
                    layout_rect=GeomRect(
                        x=30.0,
                        y=1.5,
                        width=width - 30.0,
                        height=height - 3.0,
                    ),
                ),
            ),
        ],
    )


def _metric_row_root() -> CleanDesignTreeNode:
    top = 513.2
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
        children=[
            _section_child("hero", top=100.0, height=180.0, node_type=NodeType.STACK),
            _metric_peer_stack(
                "metric-a",
                left=24.0,
                top=top,
                width=53.0,
                height=20.0,
                inner_id="metric-a-label",
            ),
            _metric_peer_stack(
                "metric-b",
                left=113.0,
                top=top + 1.6,
                width=63.0,
                height=17.0,
                inner_id="metric-b-label",
            ),
            _metric_peer_stack(
                "metric-c",
                left=212.0,
                top=top,
                width=75.0,
                height=20.0,
                inner_id="metric-c-label",
            ),
            _section_child("body", top=620.0, height=200.0, node_type=NodeType.STACK),
        ],
    )


def test_post_layout_pass_replan_assigns_slots_to_band_wrappers() -> None:
    from figma_flutter_agent.generator.normalize import (
        normalize_clean_tree,
        replan_geometry_after_layout_passes,
    )

    clean = _metric_row_root()
    screen_ir = default_screen_ir(clean)
    normalized = normalize_clean_tree(
        clean,
        screen_ir=screen_ir,
        use_geometry_planner=True,
        apply_render_safety=False,
    )
    _, after_passes = apply_ir_layout_passes(
        screen_ir,
        normalized,
        inject_root_scroll_host=True,
        validate_cp2=True,
    )
    pre_replan_violations = validate_geometry_invariants(
        after_passes,
        require_layout_slots=True,
    )
    assert any(
        violation.code == "missing_layout_slot" and violation.node_id.startswith("band-")
        for violation in pre_replan_violations
    )

    replanned = replan_geometry_after_layout_passes(after_passes)
    band = _find_node(replanned, "band-metric-a")
    assert band is not None
    assert band.layout_slot is not None
    post_replan_violations = validate_geometry_invariants(
        replanned,
        require_layout_slots=True,
    )
    assert not any(violation.code == "missing_layout_slot" for violation in post_replan_violations)


def test_sectionize_preserves_stack_paint_order_for_overlapping_peer_stacks() -> None:
    clean = _metric_row_root()
    screen_ir = default_screen_ir(clean)
    before = clean.model_copy(deep=True)
    _, after = sectionize_root_stack(
        screen_ir,
        before,
        responsive_reflow_enabled=True,
    )
    violations = check_stack_paint_order_preserved(before, after)
    assert violations == []


def test_sectionize_peer_metric_band_uses_visual_island_wrapper() -> None:
    clean = _metric_row_root()
    screen_ir = default_screen_ir(clean)
    _, after = apply_ir_layout_passes(
        screen_ir,
        clean,
        inject_root_scroll_host=True,
        validate_cp2=True,
    )
    band_nodes = [node for node in after.children if node.id.startswith("band-")]
    assert band_nodes
    metric_a = _find_node(after, "metric-a")
    assert metric_a is not None
    assert metric_a.children[0].id == "metric-a-label"


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
    assert "SingleChildScrollView" in body or "ListView(" in body
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


def _load_product_detail_vertical_root() -> CleanDesignTreeNode:
    import json
    from pathlib import Path

    payload = json.loads(
        Path("tests/fixtures/layouts/product_detail_vertical.json").read_text(encoding="utf-8"),
    )
    return CleanDesignTreeNode.model_validate(payload)


def test_sectionize_activates_for_product_detail_band_overlap() -> None:
    clean = _load_product_detail_vertical_root()
    plan = evaluate_root_sectionize(clean, responsive_reflow_enabled=True)
    assert plan.activated is True
    assert plan.bottom_chrome
    assert len(plan.scroll_sections) >= 1


def test_sectionize_root_sets_vertical_scroll_axis() -> None:
    clean = _load_product_detail_vertical_root()
    screen_ir = default_screen_ir(clean)
    updated_ir, updated_clean = sectionize_root_stack(
        screen_ir,
        clean,
        responsive_reflow_enabled=True,
    )
    assert updated_clean.scroll_axis == "vertical"
    assert updated_ir.root.layout_hints is not None
    assert updated_ir.root.layout_hints.scroll_axis == "vertical"


def test_sectionize_emits_scroll_for_product_detail_fixture() -> None:
    clean = _load_product_detail_vertical_root()
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
    assert updated_clean.type == NodeType.COLUMN
    assert "SingleChildScrollView" in body or "ListView(" in body
    assert "FittedBox(fit: BoxFit.scaleDown" not in body


def test_sectionize_disabled_when_responsive_reflow_off() -> None:
    clean = _load_product_detail_vertical_root()
    plan = evaluate_root_sectionize(clean, responsive_reflow_enabled=False)
    assert plan.activated is False
    assert plan.reject_reason == "responsive_disabled"
    screen_ir = default_screen_ir(clean)
    _, updated_clean = apply_ir_layout_passes(
        screen_ir,
        clean,
        inject_root_scroll_host=True,
        responsive_reflow_enabled=False,
        validate_cp2=False,
    )
    assert updated_clean.type == NodeType.STACK


def test_sectionize_product_detail_fixture_without_fitted_box_scale_down() -> None:
    """Corpus: vertical product-detail root reflows when responsive is enabled."""
    clean = _load_product_detail_vertical_root()
    plan = evaluate_root_sectionize(clean, responsive_reflow_enabled=True)
    assert plan.activated is True
    assert len(plan.scroll_sections) >= 1


def test_sectionize_rejects_dense_absolute_overlay_artboard() -> None:
    """Law: FixedArtboardStackPreservationLaw — dense overlay dashboards stay STACK."""
    import json
    from pathlib import Path

    from figma_flutter_agent.parser.dedup.hydrate import hydrate_pruned_cluster_instances

    payload = json.loads(
        Path(".debug/screen/limbo/9_a_home_bottom_navigation/processed.json").read_text(
            encoding="utf-8",
        ),
    )
    root = CleanDesignTreeNode.model_validate(payload["cleanTree"])
    hydrate_pruned_cluster_instances(root)
    plan = evaluate_root_sectionize(root, responsive_reflow_enabled=True)
    assert plan.activated is False
    assert plan.reject_reason == "dense_absolute_overlay_artboard"
